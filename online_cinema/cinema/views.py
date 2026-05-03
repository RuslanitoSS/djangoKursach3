import random

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Count, Prefetch
from django.db.models.functions import ExtractYear
from django.utils.translation import gettext_lazy as _
from django_filters import CharFilter, NumberFilter
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from rest_framework import filters, parsers, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import (
    Chapter, ChapterPersonRole, Comment, Episode, Franchise, Genre,
    Person, Playlist, PlaylistChapter, Rating, Review, Subscription,
    User, UserPaymentMethod, UserSubscription, ViewHistory
)
from .serializers import (
    ChapterPersonRoleSerializer, ChapterSerializer, CommentSerializer,
    EpisodeSerializer, FranchiseSerializer, GenreSerializer, PersonSerializer,
    PlaylistChapterSerializer, PlaylistSerializer, RatingSerializer,
    ReviewSerializer, SubscriptionSerializer, UserDetailSerializer,
    UserPaymentMethodSerializer, UserSerializer, UserSubscriptionSerializer,
    UserUpdateSerializer, ViewHistorySerializer
)

User = get_user_model()


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user


class IsStaffOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_staff


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
        return UserSerializer

    def get_queryset(self):
        queryset = self.queryset
        username = self.request.query_params.get('username')
        if username:
            queryset = queryset.filter(username__icontains=username)
        return queryset

    def perform_create(self, serializer):
        if not serializer.validated_data.get('login_code'):
            serializer.validated_data['login_code'] = self._generate_login_code()
        serializer.save()

    def perform_update(self, serializer):
        if 'login_code' not in self.request.data:
            serializer.validated_data.pop('login_code', None)
        serializer.save()

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
        serializer = self.get_serializer(request.user, context={'request': request})
        return Response(serializer.data)

    @staticmethod
    def _generate_login_code(length: int = 6) -> str:
        return ''.join(str(random.randint(0, 9)) for _ in range(length))


class UserPaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = UserPaymentMethod.objects.all()
    serializer_class = UserPaymentMethodSerializer


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    serializer_class = SubscriptionSerializer


class UserSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = UserSubscription.objects.all()
    serializer_class = UserSubscriptionSerializer

    def get_queryset(self):
        qs = UserSubscription.objects
        if self.action == 'list':
            qs = qs.active()
        return qs.select_related('user', 'subscription').prefetch_related('payment_methods')


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class FranchiseViewSet(viewsets.ModelViewSet):
    queryset = Franchise.objects.annotate(chapter_count=Count('chapters'))
    serializer_class = FranchiseSerializer


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

    def get_queryset(self):
        return super().get_queryset()

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()


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


class ChapterPersonRoleViewSet(viewsets.ModelViewSet):
    queryset = ChapterPersonRole.objects.all()
    serializer_class = ChapterPersonRoleSerializer


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer


class PlaylistViewSet(viewsets.ModelViewSet):
    queryset = Playlist.objects.all()
    serializer_class = PlaylistSerializer


class PlaylistChapterViewSet(viewsets.ModelViewSet):
    queryset = PlaylistChapter.objects.select_related('playlist', 'chapter').all()
    serializer_class = PlaylistChapterSerializer


class ViewHistoryViewSet(viewsets.ModelViewSet):
    queryset = ViewHistory.objects.select_related('user', 'chapter').all()
    serializer_class = ViewHistorySerializer