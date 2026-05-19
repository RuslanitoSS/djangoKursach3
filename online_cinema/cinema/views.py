import random
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch
from django.db.models.functions import ExtractYear
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters import CharFilter, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from rest_framework import filters, parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
import weasyprint

from .models import (
    Chapter, ChapterPersonRole, Comment, Episode, Franchise, Genre,
    Person, Playlist, PlaylistChapter, Rating, Review, Subscription,
    UserPaymentMethod, UserSubscription, ViewHistory
)
from .serializers import (
    ChapterPersonRoleSerializer, ChapterSerializer, CommentSerializer,
    EpisodeSerializer, FranchiseSerializer, GenreSerializer, PersonSerializer,
    PlaylistChapterSerializer, PlaylistSerializer, RatingSerializer,
    ReviewSerializer, SubscriptionSerializer, UserBriefSerializer,
    UserDetailSerializer, UserPaymentMethodSerializer, 
    UserSubscriptionSerializer, UserUpdateSerializer, ViewHistorySerializer
)

User = get_user_model()


# ================= PERMISSIONS =================
class IsOwnerOrReadOnly(permissions.BasePermission):
    """Разрешает чтение всем, а редактирование/удаление только владельцу или админу"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user or getattr(obj, 'user', None) == request.user or request.user.is_staff


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_staff


# ================= PAGINATION & FILTERS =================
class ChapterPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ChapterFilter(FilterSet):
    q = CharFilter(field_name='title', lookup_expr='icontains', label='Search by title')
    genre = CharFilter(method='filter_by_genres', label='Genres (comma-separated)')
    exclude_genre = CharFilter(method='filter_exclude_genres', label='Exclude genres (comma-separated)')
    country = CharFilter(field_name='country', lookup_expr='icontains', label='Country')
    year = NumberFilter(method='filter_by_year', label='Release year')
    content_type = CharFilter(method='filter_by_content_types', label='Content types (comma-separated)')

    class Meta:
        model = Chapter
        fields = []

    def filter_by_genres(self, queryset, name, value):
        genres = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.filter(genres__name__in=genres).distinct() if genres else queryset

    def filter_exclude_genres(self, queryset, name, value):
        genres_to_exclude = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.exclude(genres__name__in=genres_to_exclude).distinct() if genres_to_exclude else queryset

    def filter_by_year(self, queryset, name, value):
        try:
            return queryset.annotate(year=ExtractYear('release_date')).filter(year=value)
        except (ValueError, TypeError):
            return queryset

    def filter_by_content_types(self, queryset, name, value):
        types = [v.strip() for v in value.split(',') if v.strip()]
        return queryset.filter(content_type__in=types) if types else queryset


# ================= VIEWSETS =================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related().prefetch_related(
        Prefetch('groups'),
        Prefetch('user_permissions')
    )
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return UserDetailSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserBriefSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        username = self.request.query_params.get('username')
        login_code = self.request.query_params.get('login_code')
        
        if username:
            queryset = queryset.filter(username__icontains=username)
        if login_code:
            queryset = queryset.filter(login_code__contains=login_code)
        return queryset

    def perform_create(self, serializer):
        login_code = serializer.validated_data.get('login_code') or self._generate_login_code()
        serializer.save(login_code=login_code)

    def perform_update(self, serializer):
        if serializer.instance != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Вы можете изменять только свой профиль.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Вы можете удалять только свой профиль.")
        instance.delete()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def generate_login_code(self, request, pk=None):
        user = self.get_object()
        if request.user != user and not request.user.is_staff:
            self.permission_denied(request, message="Вы не можете изменить код входа этого пользователя.")
        
        user.login_code = self._generate_login_code()
        user.save(update_fields=['login_code'])
        return Response({'status': 'success', 'message': 'Код входа обновлён'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        serializer = UserDetailSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    @staticmethod
    def _generate_login_code(length: int = 6) -> str:
        return ''.join(str(random.randint(0, 9)) for _ in range(length))


class UserPaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = UserPaymentMethod.objects.all()
    serializer_class = UserPaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]


class UserSubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        base_qs = UserSubscription.objects.select_related('user', 'subscription').prefetch_related('payment_methods')
        if self.request.user.is_staff:
            return base_qs
        user_qs = base_qs.filter(user=self.request.user)
        return user_qs.active() if self.action == 'list' else user_qs

    def perform_update(self, serializer):
        sub = serializer.instance
        if sub.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        
        # Автоотмена подписки при выключении автопродления
        if 'auto_renew' in serializer.validated_data and not serializer.validated_data['auto_renew']:
            serializer.validated_data['canceled_at'] = timezone.now()
            serializer.validated_data['is_active'] = False
            
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise ValidationError("Для отмены подписки используйте обновление поля auto_renew. Удаление доступно только администраторам.")
        instance.delete()


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class FranchiseViewSet(viewsets.ModelViewSet):
    queryset = Franchise.objects.annotate(chapter_count=Count('chapters'))
    serializer_class = FranchiseSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ChapterViewSet(viewsets.ModelViewSet):
    queryset = Chapter.objects.select_related('franchise', 'required_subscription').prefetch_related('genres', 'people').order_by('-view_count')
    serializer_class = ChapterSerializer
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    pagination_class = ChapterPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ChapterFilter
    search_fields = ['title', 'description']
    ordering_fields = ['rating_cache', 'release_date', 'view_count', 'chapter_number']
    ordering = ['-view_count']

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_destroy(self, instance):
        if instance.view_count > 100:
            raise ValidationError("Нельзя удалить главу с просмотрами. Скройте её или используйте архивацию.")
        if instance.episodes.exists():
            raise ValidationError("Сначала удалите или отвяжите все связанные эпизоды.")
        instance.delete()


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.select_related('chapter').order_by('episode_number')
    serializer_class = EpisodeSerializer
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        chapter_id = self.request.query_params.get('chapter')
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        return queryset

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({"non_field_errors": _("Эпизод с таким номером уже существует в этой главе.")})

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({"non_field_errors": _("Эпизод с таким номером уже существует в этой главе.")})

    def perform_destroy(self, instance):
        if instance.chapter and instance.chapter.view_count > 50:
            raise ValidationError("Нельзя удалить эпизод из активно просматриваемой главы.")
        instance.delete()

    @action(detail=False, methods=['get'], url_path='by-chapter')
    def list_by_chapter(self, request):
        chapter_id = request.query_params.get('chapter')
        if not chapter_id:
            raise ValidationError({"chapter": _("Параметр 'chapter' обязателен.")})
        episodes = self.get_queryset().filter(chapter_id=chapter_id)
        serializer = self.get_serializer(episodes, many=True, context={'request': request})
        return Response(serializer.data)


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ChapterPersonRoleViewSet(viewsets.ModelViewSet):
    queryset = ChapterPersonRole.objects.select_related('chapter', 'person').all()
    serializer_class = ChapterPersonRoleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Вы можете редактировать только свои комментарии.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Вы можете удалять только свои комментарии.")
        instance.delete()


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class PlaylistViewSet(viewsets.ModelViewSet):
    queryset = Playlist.objects.all()
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class PlaylistChapterViewSet(viewsets.ModelViewSet):
    queryset = PlaylistChapter.objects.select_related('playlist', 'chapter').all()
    serializer_class = PlaylistChapterSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return self.queryset.filter(playlist__user=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.playlist.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.playlist.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class ViewHistoryViewSet(viewsets.ModelViewSet):
    queryset = ViewHistory.objects.select_related('user', 'chapter').all()
    serializer_class = ViewHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # История просмотров обычно только добавляется, но если нужно обновить:
        if serializer.instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


# ================= PDF GENERATION =================
@staff_member_required
def subscription_receipt_pdf(request, subscription_id):
    """Генерация PDF-квитанции для подписки пользователя"""
    subscription = get_object_or_404(UserSubscription, id=subscription_id)
    
    html = render_to_string('cinema/pdf/subscription_receipt.html', {
        'subscription': subscription,
        'user': subscription.user,
    })
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="subscription_{subscription.id}_receipt.pdf"'
    
    weasyprint.HTML(string=html).write_pdf(response)
    return response