from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment
from .serializers import (
    FanClubSerializer, FanClubCreateSerializer,
    FanClubMembershipSerializer, FanClubMembershipCreateSerializer, FanClubMembershipRoleSerializer,
    FanClubPhotoSerializer, FanClubApplicationAttachmentSerializer
)


class IsClubAdminOrReadOnly(permissions.BasePermission):
    """Разрешение: чтение всем, запись только админам клуба"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.has_admin(request.user)


class IsClubAdmin(permissions.BasePermission):
    """Разрешение: только админы клуба"""
    def has_object_permission(self, request, view, obj):
        return obj.has_admin(request.user)


class IsCreatorOrAdmin(permissions.BasePermission):
    """Разрешение: создатель или админ"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.is_creator(request.user) or obj.has_admin(request.user)


# ==============================================================================
# VIEWSETS
# ==============================================================================

class FanClubViewSet(viewsets.ModelViewSet):
    queryset = FanClub.objects.filter(is_active=True)
    lookup_field = 'slug'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsClubAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return FanClubCreateSerializer
        return FanClubSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def memberships(self, request, slug=None):
        """Получить всех участников клуба"""
        club = self.get_object()
        memberships = club.memberships.select_related('user').all()
        serializer = FanClubMembershipSerializer(memberships, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pending_applications(self, request, slug=None):
        """Получить заявки на проверку (только для админов)"""
        club = self.get_object()
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут просматривать заявки'}, status=403)
        
        memberships = club.memberships.filter(status='pending').select_related('user')
        serializer = FanClubMembershipSerializer(memberships, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def upload_photo(self, request, slug=None):
        """Загрузить фото в галерею клуба"""
        club = self.get_object()
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут загружать фото'}, status=403)
        
        if not club.can_add_club_photo():
            return Response({'detail': 'Достигнут лимит фото в галерее'}, status=400)
        
        photo_file = request.FILES.get('photo')
        caption = request.data.get('caption', '')
        
        if not photo_file:
            return Response({'detail': 'Файл не предоставлен'}, status=400)
        
        club_photo = FanClubPhoto.objects.create(
            club=club,
            photo=photo_file,
            caption=caption,
            uploaded_by=request.user
        )
        
        serializer = FanClubPhotoSerializer(club_photo)
        return Response(serializer.data, status=201)


class FanClubMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = FanClubMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FanClubMembership.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return FanClubMembershipCreateSerializer
        elif self.action in ['promote', 'demote']:
            return FanClubMembershipRoleSerializer
        return FanClubMembershipSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Одобрить заявку (только админ клуба)"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут одобрять заявки'}, status=403)
        
        if membership.status != 'pending':
            return Response({'detail': 'Заявка уже обработана'}, status=400)
        
        membership.approve(request.user)
        serializer = self.get_serializer(membership, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Отклонить заявку (только админ клуба)"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут отклонять заявки'}, status=403)
        
        if membership.status != 'pending':
            return Response({'detail': 'Заявка уже обработана'}, status=400)
        
        comment = request.data.get('comment', 'Отклонено администратором')
        membership.reject(request.user, comment)
        serializer = self.get_serializer(membership, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        """Повысить до администратора"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут назначать админов'}, status=403)
        
        try:
            membership.promote_to_admin(request.user)
            serializer = self.get_serializer(membership, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def demote(self, request, pk=None):
        """Понизить до участника"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут понижать админов'}, status=403)
        
        try:
            membership.demote_to_member(request.user)
            serializer = self.get_serializer(membership, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)


class FanClubApplicationAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = FanClubApplicationAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return FanClubApplicationAttachment.objects.filter(membership__user=user)

    def perform_create(self, serializer):
        membership_id = self.request.data.get('membership')
        membership = get_object_or_404(FanClubMembership, id=membership_id, user=self.request.user)
        
        if membership.status != 'pending':
            raise serializers.ValidationError("Нельзя добавлять фото к обработанной заявке")
        
        if not membership.can_add_more_application_photos():
            raise serializers.ValidationError("Достигнут лимит фото в заявке")
        
        serializer.save(membership=membership)

    @action(detail=True, methods=['post'])
    def move_to_gallery(self, request, pk=None):
        """Перенести фото в галерею клуба (только админ)"""
        attachment = self.get_object()
        club = attachment.membership.club
        
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут переносить фото'}, status=403)
        
        try:
            caption = request.data.get('caption', attachment.caption)
            club_photo = attachment.move_to_club_gallery(caption=caption, uploaded_by=request.user)
            return Response({'detail': 'Фото перенесено в галерею', 'photo_id': club_photo.id})
        except Exception as e:
            return Response({'detail': str(e)}, status=400)