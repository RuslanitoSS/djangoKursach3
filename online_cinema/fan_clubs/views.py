from django.db import transaction
from django.db.models import Count, Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import FanClub, FanClubPhoto, FanClubMembership, FanClubApplicationAttachment
from .serializers import (
    FanClubSerializer, FanClubCreateSerializer,
    FanClubMembershipSerializer, FanClubMembershipCreateSerializer, FanClubMembershipRoleSerializer,
    FanClubPhotoSerializer, FanClubApplicationAttachmentSerializer
)


# ==============================================================================
# PERMISSIONS
# ==============================================================================
class IsClubAdminOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.has_admin(request.user)


class IsClubAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.has_admin(request.user)


class IsCreatorOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.is_creator(request.user) or obj.has_admin(request.user)


# ==============================================================================
# VIEWSETS
# ==============================================================================

class FanClubViewSet(viewsets.ModelViewSet):
    queryset = FanClub.objects.filter(is_active=True)
    lookup_field = 'id'
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsClubAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return FanClubCreateSerializer
        return FanClubSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        club = serializer.instance
        output_serializer = FanClubSerializer(club, context={'request': request})
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        if request.user.is_authenticated:
            data['is_admin'] = instance.has_admin(request.user) or instance.is_creator(request.user)
        else:
            data['is_admin'] = False
        return Response(data)

    @action(detail=True, methods=['get'])
    def photos(self, request, id=None):
        club = self.get_object()
        photos = club.photos.all()
        serializer = FanClubPhotoSerializer(photos, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def memberships(self, request, id=None):
        club = self.get_object()
        memberships = club.memberships.select_related('user').all()
        serializer = FanClubMembershipSerializer(memberships, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pending_applications(self, request, id=None):
        club = self.get_object()
        if not club.has_admin(request.user):
            return Response({'detail': 'Только администраторы могут просматривать заявки'}, status=403)
        memberships = club.memberships.filter(status='pending').select_related('user')
        serializer = FanClubMembershipSerializer(memberships, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def upload_photo(self, request, id=None):
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
            club=club, photo=photo_file, caption=caption, uploaded_by=request.user
        )
        serializer = FanClubPhotoSerializer(club_photo)
        return Response(serializer.data, status=201)

    @action(detail=False, methods=['get'], pagination_class=None)
    def popular(self, request):
        popular_clubs = (
            self.get_queryset()
            .annotate(
                active_members_count=Count('memberships', filter=Q(memberships__status='approved'))
            )
            .order_by('-active_members_count', '-created_at')[:10]
        )
        serializer = self.get_serializer(popular_clubs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return self.popular(request)
        clubs = self.get_queryset().filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(franchise__title__icontains=query)
        ).distinct()
        clubs = clubs.annotate(
            active_members_count=Count('memberships', filter=Q(memberships__status='approved'))
        ).order_by('-active_members_count', '-created_at')
        serializer = self.get_serializer(clubs, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='upload_cover_photo')
    def upload_cover_photo(self, request, id=None):
        club = self.get_object()
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут изменять обложку клуба'},
                status=status.HTTP_403_FORBIDDEN
            )
        cover_file = request.FILES.get('cover_photo')
        if not cover_file:
            return Response({'detail': 'Файл не предоставлен'}, status=status.HTTP_400_BAD_REQUEST)
        max_size = 10 * 1024 * 1024
        if cover_file.size > max_size:
            return Response(
                {'detail': f'Размер обложки не должен превышать 10 МБ (получено {cover_file.size / 1024 / 1024:.2f} МБ)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        allowed_types = ['image/jpeg', 'image/png', 'image/jpg']
        if cover_file.content_type not in allowed_types:
            return Response({'detail': 'Допустимые форматы: JPG, PNG'}, status=status.HTTP_400_BAD_REQUEST)
        if club.cover_photo:
            try:
                old_cover = club.cover_photo
                club.cover_photo = cover_file
                club.save(update_fields=['cover_photo'])
                old_cover.delete(save=False)
            except Exception as e:
                return Response(
                    {'detail': f'Ошибка при обновлении обложки: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            club.cover_photo = cover_file
            club.save(update_fields=['cover_photo'])
        serializer = FanClubSerializer(club, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.has_admin(request.user) and not instance.is_creator(request.user):
            return Response(
                {'detail': 'Только администраторы или создатель могут удалить клуб'},
                status=status.HTTP_403_FORBIDDEN
            )
        if instance.cover_photo:
            instance.cover_photo.delete(save=False)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def join(self, request, id=None):
        club = self.get_object()
        if not club.is_active:
            return Response({'detail': 'Клуб скрыт или неактивен'}, status=status.HTTP_400_BAD_REQUEST)

        existing = FanClubMembership.objects.filter(
            user=request.user,
            club=club,
            status__in=['pending', 'approved']
        ).first()

        if existing:
            if existing.status == 'approved':
                return Response(
                    {'detail': 'Вы уже являетесь участником этого клуба'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {'detail': 'У вас уже есть заявка на вступление в этот клуб'},
                status=status.HTTP_400_BAD_REQUEST
            )

        auto_approve = not club.application_questions and not club.requirements_text

        membership = FanClubMembership.objects.create(
            user=request.user,
            club=club,
            role='member',
            status='approved' if auto_approve else 'pending',
            joined_at=timezone.now() if auto_approve else None,
        )

        serializer = FanClubMembershipSerializer(membership, context={'request': request})
        detail = (
            'Вы успешно вступили в клуб' if auto_approve
            else 'Заявка на вступление отправлена и ожидает одобрения'
        )

        return Response(
            {'detail': detail, 'membership': serializer.data},
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def leave(self, request, id=None):
        club = self.get_object()

        membership = FanClubMembership.objects.filter(
            user=request.user,
            club=club,
            status='approved'
        ).first()

        if not membership:
            return Response(
                {'detail': 'Вы не являетесь участником этого клуба'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            is_admin = membership.role == 'admin'
            is_creator = club.is_creator(request.user)

            approved_memberships = club.memberships.filter(status='approved')
            total_members = approved_memberships.count()

            if total_members == 1:
                for photo in club.photos.all():
                    if photo.photo:
                        photo.photo.delete(save=False)
                if club.cover_photo:
                    club.cover_photo.delete(save=False)
                club.delete()
                return Response(
                    {'detail': 'Вы покинули клуб. Клуб был удалён, так как вы были последним участником.'},
                    status=status.HTTP_200_OK
                )

            new_admin_info = None
            if is_admin:
                admins_count = approved_memberships.filter(role='admin').count()
                if admins_count == 1:
                    new_admin = (
                        approved_memberships
                        .exclude(user=request.user)
                        .filter(role='member')
                        .order_by('joined_at')
                        .first()
                    )
                    if not new_admin:
                        new_admin = (
                            approved_memberships
                            .exclude(user=request.user)
                            .order_by('joined_at')
                            .first()
                        )

                    if new_admin:
                        new_admin.role = 'admin'
                        new_admin.save(update_fields=['role'])
                        new_admin_info = {
                            'id': new_admin.id,
                            'username': new_admin.user.username,
                        }

            if is_creator:
                club.created_by = None
                club.save(update_fields=['created_by'])

            membership.delete()

        response_data = {'detail': 'Вы успешно покинули клуб'}
        if new_admin_info:
            response_data['new_admin'] = new_admin_info
            response_data['detail'] += f'. Администратором назначен пользователь {new_admin_info["username"]}.'

        return Response(response_data, status=status.HTTP_200_OK)


# ==============================================================================
# 👇 ИСПРАВЛЕННЫЙ FanClubMembershipViewSet
# ==============================================================================
class FanClubMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = FanClubMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'  # 👈 ДОБАВЛЕНО!

    def get_queryset(self):
        user = self.request.user
        
        # Для админских действий — заявки клубов, где пользователь админ
        if self.action in ['approve', 'reject', 'promote', 'demote']:
            admin_club_ids = FanClubMembership.objects.filter(
                user=user,
                role='admin',
                status='approved'
            ).values_list('club_id', flat=True)
            return FanClubMembership.objects.filter(club_id__in=admin_club_ids)
        
        # По умолчанию — только свои заявки
        return FanClubMembership.objects.filter(user=user)

    def get_serializer_class(self):
        if self.action == 'create':
            return FanClubMembershipCreateSerializer
        elif self.action in ['promote', 'demote']:
            return FanClubMembershipRoleSerializer
        return FanClubMembershipSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, *args, **kwargs):  # 👈 УБРАЛИ id=None
        """Одобрить заявку (только админ клуба)"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут одобрять заявки'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if membership.status != 'pending':
            return Response(
                {'detail': 'Заявка уже обработана'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        membership.approve(request.user)
        serializer = self.get_serializer(membership, context={'request': request})
        return Response({
            'detail': f'Заявка пользователя {membership.user.username} одобрена',
            'membership': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, *args, **kwargs):  # 👈 УБРАЛИ id=None
        """Отклонить заявку (только админ клуба)"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут отклонять заявки'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        if membership.status != 'pending':
            return Response(
                {'detail': 'Заявка уже обработана'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        comment = request.data.get('comment', 'Отклонено администратором')
        membership.reject(request.user, comment)
        serializer = self.get_serializer(membership, context={'request': request})
        return Response({
            'detail': f'Заявка пользователя {membership.user.username} отклонена',
            'membership': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def promote(self, request, *args, **kwargs):  # 👈 УБРАЛИ id=None
        """Повысить до администратора"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут назначать админов'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            membership.promote_to_admin(request.user)
            serializer = self.get_serializer(membership, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def demote(self, request, *args, **kwargs):  # 👈 УБРАЛИ id=None
        """Понизить до участника"""
        membership = self.get_object()
        club = membership.club
        
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут понижать админов'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            membership.demote_to_member(request.user)
            serializer = self.get_serializer(membership, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# ==============================================================================
# 👇 ИСПРАВЛЕННЫЙ FanClubApplicationAttachmentViewSet
# ==============================================================================
class FanClubApplicationAttachmentViewSet(viewsets.ModelViewSet):
    serializer_class = FanClubApplicationAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'  # 👈 ДОБАВЛЕНО!

    def get_queryset(self):
        user = self.request.user
        
        # Для move_to_gallery — заявки в клубах, где пользователь админ
        if self.action == 'move_to_gallery':
            admin_club_ids = FanClubMembership.objects.filter(
                user=user,
                role='admin',
                status='approved'
            ).values_list('club_id', flat=True)
            return FanClubApplicationAttachment.objects.filter(
                membership__club_id__in=admin_club_ids
            )
        
        # По умолчанию — только свои вложения
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
    def move_to_gallery(self, request, *args, **kwargs):  # 👈 УБРАЛИ id=None
        """Перенести фото в галерею клуба (только админ)"""
        attachment = self.get_object()
        club = attachment.membership.club
        
        if not club.has_admin(request.user):
            return Response(
                {'detail': 'Только администраторы могут переносить фото'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            caption = request.data.get('caption', attachment.caption)
            club_photo = attachment.move_to_club_gallery(caption=caption, uploaded_by=request.user)
            return Response({'detail': 'Фото перенесено в галерею', 'photo_id': club_photo.id})
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)