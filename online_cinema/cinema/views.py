import random
from django.db import connection, reset_queries
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Avg
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
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, parsers, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    Chapter,
    ChapterPersonRole,
    Comment,
    Episode,
    Franchise,
    Genre,
    Person,
    Playlist,
    PlaylistChapter,
    Rating,
    Review,
    Subscription,
    UserPaymentMethod,
    UserSubscription,
    ViewHistory,
)
from .serializers import (
    ChapterPersonRoleSerializer,
    ChapterSerializer,
    CommentSerializer,
    EpisodeSerializer,
    FranchiseSerializer,
    GenreSerializer,
    PersonSerializer,
    PlaylistChapterSerializer,
    PlaylistSerializer,
    RatingSerializer,
    ReviewSerializer,
    SubscriptionSerializer,
    UserBriefSerializer,
    UserDetailSerializer,
    UserPaymentMethodSerializer,
    UserSubscriptionSerializer,
    UserUpdateSerializer,
    ViewHistorySerializer,
    ChapterDetailSerializer,
    RelatedChapterSerializer,
    AdminUserBriefSerializer,
    AdminUserDetailSerializer,
    AdminUserUpdateSerializer,
    AvailableRoleSerializer,
)

User = get_user_model()

# cinema/views/auth.py
from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from cinema.serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    LogoutSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Логин: выдаёт access + refresh токены"""

    serializer_class = CustomTokenObtainPairSerializer


class CustomTokenRefreshView(TokenRefreshView):
    """Обновление access токена по refresh"""

    pass


class RegisterView(generics.CreateAPIView):
    """Регистрация нового пользователя"""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Сразу выдаём токены после регистрации
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(generics.GenericAPIView):
    """Логаут: добавляет refresh токен в чёрный список"""

    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


class MeView(generics.RetrieveAPIView):
    """Получение данных текущего пользователя"""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        from cinema.serializers import UserDetailSerializer

        return UserDetailSerializer

    def get_object(self):
        return self.request.user


# ================= PERMISSIONS =================
class IsOwnerOrReadOnly(permissions.BasePermission):
    """Разрешает чтение всем, а редактирование/удаление только владельцу или админу"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            obj == request.user
            or getattr(obj, "user", None) == request.user
            or request.user.is_staff
        )


class IsStaffOrReadOnly(permissions.BasePermission):
    """Разрешает чтение (GET) всем, а запись/удаление только персоналу"""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True  # ✅ Теперь чтение доступно всем без авторизации
        return request.user.is_staff


# ================= PAGINATION & FILTERS =================
class ChapterPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ChapterFilter(FilterSet):
    q = CharFilter(field_name="title", lookup_expr="icontains", label="Search by title")
    genre = CharFilter(method="filter_by_genres", label="Genres (comma-separated)")
    exclude_genre = CharFilter(
        method="filter_exclude_genres", label="Exclude genres (comma-separated)"
    )
    country = CharFilter(field_name="country", lookup_expr="icontains", label="Country")
    year = NumberFilter(method="filter_by_year", label="Release year")
    content_type = CharFilter(
        method="filter_by_content_types", label="Content types (comma-separated)"
    )

    class Meta:
        model = Chapter
        fields = []

    def filter_by_genres(self, queryset, name, value):
        genres = [v.strip() for v in value.split(",") if v.strip()]
        return (
            queryset.filter(genres__name__in=genres).distinct() if genres else queryset
        )

    def filter_exclude_genres(self, queryset, name, value):
        genres_to_exclude = [v.strip() for v in value.split(",") if v.strip()]
        return (
            queryset.exclude(genres__name__in=genres_to_exclude).distinct()
            if genres_to_exclude
            else queryset
        )

    def filter_by_year(self, queryset, name, value):
        try:
            return queryset.annotate(year=ExtractYear("release_date")).filter(
                year=value
            )
        except (ValueError, TypeError):
            return queryset

    def filter_by_content_types(self, queryset, name, value):
        types = [v.strip() for v in value.split(",") if v.strip()]
        return queryset.filter(content_type__in=types) if types else queryset


# ================= VIEWSETS =================
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related(
        Prefetch("groups"), Prefetch("user_permissions")
    )
    # 🔒 Базовые права: аутентификация + владелец/админ
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: переопределяем права для list/retrieve
    def get_permissions(self):
        """
        Разграничение прав по действиям:
        - list, retrieve → только админы (IsAdminUser)
        - остальные действия → базовые permission_classes
        """
        if self.action in ["list", "retrieve"]:
            return [permissions.IsAdminUser()]
        return [permission() for permission in self.permission_classes]

    def get_serializer_class(self):
        # 🔥 Используем админские сериализаторы для админских действий
        if self.action == "list":
            return AdminUserBriefSerializer
        if self.action == "retrieve":
            return AdminUserDetailSerializer
        if self.action in ["update", "partial_update"]:
            # Если админ — используем админский, иначе обычный
            if self.request.user.is_staff:
                return AdminUserUpdateSerializer
            return UserUpdateSerializer
        return UserBriefSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        username = self.request.query_params.get("username")
        login_code = self.request.query_params.get("login_code")
        search = self.request.query_params.get("search")

        if username:
            queryset = queryset.filter(username__icontains=username)
        if login_code:
            queryset = queryset.filter(login_code__contains=login_code)

        # 🔥 Расширенный поиск для админки
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )

        # 🔥 Фильтры для админки
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        role = self.request.query_params.get("role")
        if role == "superuser":
            queryset = queryset.filter(is_superuser=True)
        elif role == "staff":
            queryset = queryset.filter(is_staff=True, is_superuser=False)
        elif role == "user":
            queryset = queryset.filter(is_staff=False, is_superuser=False)

        group_id = self.request.query_params.get("group")
        if group_id:
            queryset = queryset.filter(groups__id=group_id)

        return queryset.distinct()

    def perform_create(self, serializer):
        login_code = (
            serializer.validated_data.get("login_code") or self._generate_login_code()
        )
        serializer.save(login_code=login_code)

    def perform_update(self, serializer):
        if serializer.instance != self.request.user and not self.request.user.is_staff:
            self.permission_denied(
                self.request, "Вы можете изменять только свой профиль."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if instance != self.request.user and not self.request.user.is_staff:
            self.permission_denied(
                self.request, "Вы можете удалять только свой профиль."
            )
        instance.delete()

    # ================= АДМИНСКИЕ ДЕЙСТВИЯ =================

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def block(self, request, pk=None):
        """🚫 Блокировка пользователя (is_active=False)"""
        user = self.get_object()

        if user == request.user:
            return Response(
                {"detail": "Вы не можете заблокировать себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_superuser and not request.user.is_superuser:
            return Response(
                {
                    "detail": "Только суперпользователь может блокировать суперпользователей."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user.is_active = False
        user.save(update_fields=["is_active"])

        return Response(
            {
                "status": "blocked",
                "detail": f"Пользователь {user.username} заблокирован",
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def unblock(self, request, pk=None):
        """✅ Разблокировка пользователя (is_active=True)"""
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active"])

        return Response(
            {
                "status": "unblocked",
                "detail": f"Пользователь {user.username} разблокирован",
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def change_role(self, request, pk=None):
        """
        Изменение роли пользователя
        Body: { "role": "user" | "staff" | "superuser" }
        """
        user = self.get_object()
        new_role = request.data.get("role")

        if new_role not in ["user", "staff", "superuser"]:
            return Response(
                {"detail": "Недопустимая роль. Используйте: user, staff, superuser"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Защита от снятия прав с себя
        if user == request.user:
            return Response(
                {"detail": "Вы не можете изменить свою собственную роль."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Применяем роль
        if new_role == "superuser":
            user.is_superuser = True
            user.is_staff = True
        elif new_role == "staff":
            user.is_superuser = False
            user.is_staff = True
        else:  # user
            user.is_superuser = False
            user.is_staff = False

        user.save(update_fields=["is_superuser", "is_staff"])

        return Response(
            {
                "status": "role_changed",
                "detail": f"Роль {user.username} изменена на {new_role}",
                "new_role": new_role,
            }
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAdminUser])
    def stats(self, request):
        """📊 Статистика пользователей для админки"""
        from django.db.models import Count

        total = User.objects.count()
        active = User.objects.filter(is_active=True).count()
        blocked = User.objects.filter(is_active=False).count()
        staff = User.objects.filter(is_staff=True).count()
        superusers = User.objects.filter(is_superuser=True).count()

        # Статистика по группам
        groups_stats = Group.objects.annotate(
            users_count=Count("custom_user_set")
        ).values("id", "name", "users_count")

        return Response(
            {
                "total": total,
                "active": active,
                "blocked": blocked,
                "staff": staff,
                "superusers": superusers,
                "groups": list(groups_stats),
            }
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAdminUser])
    def roles(self, request):
        """🏷️ Список всех доступных ролей (групп)"""
        groups = Group.objects.all()
        serializer = AvailableRoleSerializer(groups, many=True)
        return Response(serializer.data)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def change_password(self, request, pk=None):
        """Смена пароля пользователя"""
        user = self.get_object()

        # Проверка: пользователь может менять только свой пароль
        if user != request.user and not request.user.is_staff:
            return Response(
                {"detail": "Вы можете менять только свой пароль"},
                status=status.HTTP_403_FORBIDDEN,
            )

        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response(
                {"detail": "Необходимо указать текущий и новый пароль"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Проверка текущего пароля
        if not user.check_password(old_password):
            return Response(
                {"old_password": "Неверный текущий пароль"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Валидация нового пароля
        if len(new_password) < 8:
            return Response(
                {"new_password": "Пароль должен содержать минимум 8 символов"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Устанавливаем новый пароль
        user.set_password(new_password)
        user.save()

        return Response({"detail": "Пароль успешно изменён"}, status=status.HTTP_200_OK)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def generate_login_code(self, request, pk=None):
        user = self.get_object()
        if request.user != user and not request.user.is_staff:
            self.permission_denied(
                request, message="Вы не можете изменить код входа этого пользователя."
            )

        user.login_code = self._generate_login_code()
        user.save(update_fields=["login_code"])
        return Response(
            {"status": "success", "message": "Код входа обновлён"},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        serializer = UserDetailSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    @staticmethod
    def _generate_login_code(length: int = 6) -> str:
        return "".join(str(random.randint(0, 9)) for _ in range(length))


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
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
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
        base_qs = UserSubscription.objects.select_related(
            "user", "subscription"
        ).prefetch_related("payment_methods")
        if self.request.user.is_staff:
            return base_qs
        user_qs = base_qs.filter(user=self.request.user)
        return user_qs.active() if self.action == "list" else user_qs

    def perform_update(self, serializer):
        sub = serializer.instance
        if sub.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")

        # Автоотмена подписки при выключении автопродления
        if (
            "auto_renew" in serializer.validated_data
            and not serializer.validated_data["auto_renew"]
        ):
            serializer.validated_data["canceled_at"] = timezone.now()
            serializer.validated_data["is_active"] = False

        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise ValidationError(
                "Для отмены подписки используйте обновление поля auto_renew. Удаление доступно только администраторам."
            )
        instance.delete()


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class FranchiseViewSet(viewsets.ModelViewSet):
    queryset = Franchise.objects.annotate(chapter_count=Count("chapters"))
    serializer_class = FranchiseSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ChapterViewSet(viewsets.ModelViewSet):
    queryset = (
        Chapter.objects.select_related("franchise", "required_subscription")
        .order_by("-view_count")
    )

    serializer_class = ChapterSerializer

    # Базовое разрешение: читать могут все, менять/удалять только стафф
    permission_classes = [IsStaffOrReadOnly]

    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    pagination_class = ChapterPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = ChapterFilter
    search_fields = ["title", "description"]
    ordering_fields = ["rating_cache", "release_date", "view_count", "chapter_number"]
    ordering = ["-view_count"]

    def get_serializer_class(self):
        """Используем расширенный сериализатор для retrieve"""
        if self.action == "retrieve":
            return ChapterDetailSerializer
        return ChapterSerializer

    def perform_update(self, serializer):
        with transaction.atomic():
            serializer.save()

    def perform_destroy(self, instance):
        if instance.view_count > 100:
            raise ValidationError(
                "Нельзя удалить главу с просмотрами. Скройте её или используйте архивацию."
            )
        if instance.episodes.exists():
            raise ValidationError("Сначала удалите или отвяжите все связанные эпизоды.")
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        """
        Расширенный retrieve с похожим контентом.
        GET /api/v1/chapters/{id}/
        """
        instance = self.get_object()

        # Основной сериализатор
        serializer = self.get_serializer(instance, context={"request": request})
        data = serializer.data

        # Добавляем похожий контент
        related_chapters = self._get_related_chapters(instance)
        related_serializer = RelatedChapterSerializer(
            related_chapters, many=True, context={"request": request}
        )
        data["related"] = related_serializer.data

        return Response(data)

    def _get_related_chapters(self, chapter, limit=8):
        """
        Получает похожие главы на основе:
        1. Той же франшизы
        2. Тех же жанров
        3. Схожего рейтинга
        """
        # Сначала пробуем найти в той же франшизе
        if chapter.franchise:
            related = Chapter.objects.filter(franchise=chapter.franchise).exclude(
                id=chapter.id
            )
        else:
            # Иначе ищем по жанрам
            related = (
                Chapter.objects.filter(genres__in=chapter.genres.all())
                .exclude(id=chapter.id)
                .distinct()
            )

        # Добавляем аннотацию с рейтингом и сортируем
        related = related.annotate(avg_rating=Avg("ratings__score")).order_by(
            "-avg_rating", "-view_count", "-release_date"
        )[:limit]

        return list(related)

    # ================= НАЧАЛО: СЕКЦИИ ГЛАВНОЙ СТРАНИЦЫ =================

    def _get_base_chapters(self):
        """
        Общий queryset для всех секций главной страницы.
        Топ-8 глав по среднему рейтингу и дате выхода (новые и популярные).
        """
        return list(
            self.get_queryset()
            .annotate(avg_rating=Avg("ratings__score"))
            .order_by("-avg_rating", "-release_date")[:8]
        )

    @action(detail=False, methods=["get"], pagination_class=None)
    def now_playing(self, request):
        """Сейчас в эфире: те же 8 глав, перемешанные"""
        chapters = self._get_base_chapters()
        random.shuffle(chapters)
        return Response(self.get_serializer(chapters, many=True).data)

    @action(detail=False, methods=["get"], pagination_class=None)
    def for_you(self, request):
        """Для вас: те же 8 глав, перемешанные"""
        chapters = self._get_base_chapters()
        random.shuffle(chapters)
        return Response(self.get_serializer(chapters, many=True).data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated],
        pagination_class=None,
    )
    def continue_watching(self, request):
        """
        Продолжить просмотр: история пользователя + популярные.
        """
        history = (
            ViewHistory.objects.filter(user=request.user)
            .select_related("chapter")
            .order_by("-viewed_at")[:7]
        )
        history_chapters = [h.chapter for h in history]
        history_ids = [c.id for c in history_chapters]

        remaining = max(0, 8 - len(history_chapters))
        popular = (
            self.get_queryset()
            .exclude(id__in=history_ids)
            .annotate(avg_rating=Avg("ratings__score"))
            .order_by("-avg_rating", "-release_date")[:remaining]
        )

        combined = history_chapters + list(popular)
        return Response(self.get_serializer(combined, many=True).data)

    @action(detail=False, methods=["get"], pagination_class=None)
    def top_10(self, request):
        """Топ-10: лучший рейтинг + просмотры"""
        chapters = (
            self.get_queryset()
            .annotate(avg_rating=Avg("ratings__score"))
            .order_by("-avg_rating", "-view_count")[:10]
        )

        serializer = self.get_serializer(chapters, many=True)
        data = serializer.data

        # Добавляем avg_rating в ответ
        for i, chapter in enumerate(chapters):
            data[i]["avg_rating"] = round(chapter.avg_rating or 0, 2)

        return Response(data)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def add_to_watchlist(self, request, pk=None):
        """Добавить в избранное (watchlist)"""
        chapter = self.get_object()
        playlist, created = Playlist.objects.get_or_create(
            user=request.user, is_favorite=True, defaults={"title": "Избранное"}
        )

        playlist_chapter, created = PlaylistChapter.objects.get_or_create(
            playlist=playlist, chapter=chapter
        )

        if not created:
            return Response(
                {"detail": "Уже в избранном"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"detail": "Добавлено в избранное"}, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def remove_from_watchlist(self, request, pk=None):
        """Удалить из избранного"""
        chapter = self.get_object()
        playlist = Playlist.objects.filter(user=request.user, is_favorite=True).first()

        if not playlist:
            return Response(
                {"detail": "Избранное не найдено"}, status=status.HTTP_404_NOT_FOUND
            )

        PlaylistChapter.objects.filter(playlist=playlist, chapter=chapter).delete()

        return Response({"detail": "Удалено из избранного"}, status=status.HTTP_200_OK)

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def rate(self, request, pk=None):
        """Оценить фильм/сериал (1-10)"""
        chapter = self.get_object()
        score = request.data.get("score")

        if not score or not (1 <= int(score) <= 10):
            return Response(
                {"detail": "Оценка должна быть от 1 до 10"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rating, created = Rating.objects.update_or_create(
            user=request.user, chapter=chapter, defaults={"score": int(score)}
        )

        # Обновляем кэш рейтинга
        avg = chapter.ratings.aggregate(avg=Avg("score"))["avg"]
        chapter.rating_cache = avg or 0
        chapter.save(update_fields=["rating_cache"])

        return Response(
            {
                "detail": "Оценка сохранена",
                "score": rating.score,
                "avg_rating": round(chapter.rating_cache, 2),
            }
        )

    @action(
        detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated]
    )
    def mark_watched(self, request, pk=None):
        """Отметить как просмотренное (добавить в историю)"""
        chapter = self.get_object()

        ViewHistory.objects.update_or_create(
            user=request.user, chapter=chapter, defaults={"viewed_at": timezone.now()}
        )

        # Увеличиваем счётчик просмотров
        chapter.view_count += 1
        chapter.save(update_fields=["view_count"])

        return Response({"detail": "Просмотр отмечен"}, status=status.HTTP_200_OK)

    # ================= КОНЕЦ: СЕКЦИИ ГЛАВНОЙ СТРАНИЦЫ ================


class EpisodeViewSet(viewsets.ModelViewSet):
    queryset = Episode.objects.order_by("episode_number")
    serializer_class = EpisodeSerializer
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        chapter_id = self.request.query_params.get("chapter")
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        return queryset

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError(
                {
                    "non_field_errors": _(
                        "Эпизод с таким номером уже существует в этой главе."
                    )
                }
            )

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError(
                {
                    "non_field_errors": _(
                        "Эпизод с таким номером уже существует в этой главе."
                    )
                }
            )

    def perform_destroy(self, instance):
        if instance.chapter and instance.chapter.view_count > 50:
            raise ValidationError(
                "Нельзя удалить эпизод из активно просматриваемой главы."
            )
        instance.delete()

    @action(detail=False, methods=["get"], url_path="by-chapter")
    def list_by_chapter(self, request):
        chapter_id = request.query_params.get("chapter")
        if not chapter_id:
            raise ValidationError({"chapter": _("Параметр 'chapter' обязателен.")})
        episodes = self.get_queryset().filter(chapter_id=chapter_id)
        serializer = self.get_serializer(
            episodes, many=True, context={"request": request}
        )
        return Response(serializer.data)


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    @action(detail=False, methods=["get"], pagination_class=None)
    def popular(self, request):
        """Топ-5 популярных персон (по количеству ролей)"""
        from django.db.models import Count

        popular_persons = (
            self.get_queryset()
            .annotate(roles_count=Count("person_roles"))
            .filter(roles_count__gt=0)  # Только те, у кого есть роли
            .order_by("-roles_count", "-birth_date")[:6]
        )
        serializer = self.get_serializer(
            popular_persons, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ChapterPersonRoleViewSet(viewsets.ModelViewSet):
    queryset = ChapterPersonRole.objects.select_related("chapter", "person").all()
    serializer_class = ChapterPersonRoleSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]

# ================= CUSTOM PERMISSION =================
class IsOwnerOrStaff(permissions.BasePermission):
    """
    Разрешает доступ только если:
    - пользователь является администратором (is_staff), ИЛИ
    - пользователь является автором объекта (объект имеет атрибут user)
    """
    def has_permission(self, request, view):
        # Базовая проверка: пользователь должен быть авторизован
        # (для update/delete/create это обязательно)
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Разрешаем админам всё
        if request.user.is_staff:
            return True
        # Разрешаем автору объекта редактировать/удалять свой комментарий
        return getattr(obj, "user", None) == request.user


# ================= VIEWSET =================
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.select_related(
        "user",
        "chapter",
        "chapter__franchise",
        "chapter__required_subscription"
    ).prefetch_related(
        "chapter__genres",
        "chapter__people",
    ).order_by("-created_at")
    serializer_class = CommentSerializer
    
    # Базовое разрешение: читают все, остальное — динамически
    permission_classes = [permissions.AllowAny]

    def get_permissions(self):
        """
        Динамическое назначение прав в зависимости от действия:
        - GET (list/retrieve): любой пользователь (включая анонимов)
        - POST (create): только авторизованные
        - PUT/PATCH/DELETE: только автор комментария или админ (через IsOwnerOrStaff)
        """
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        elif self.action == "create":
            return [permissions.IsAuthenticated()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsOwnerOrStaff()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset()
        chapter_id = self.request.query_params.get("chapter")
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        return queryset

    def perform_create(self, serializer):
        # При создании автоматически привязываем комментарий к текущему пользователю
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Дополнительная проверка на уровне объекта (дублирует permission для надёжности)
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
            self.permission_denied(
                self.request, "Вы можете редактировать только свои комментарии."
            )
        serializer.save()

    def perform_destroy(self, instance):
        # Дополнительная проверка на уровне объекта
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(
                self.request, "Вы можете удалять только свои комментарии."
            )
        instance.delete()

# ================= VIEWSET =================
class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.select_related("user", "chapter").all()
    serializer_class = ReviewSerializer
    
    # Базовое разрешение — динамически в get_permissions()
    permission_classes = []

    def get_permissions(self):
        """
        Динамические права доступа:
        - GET (list/retrieve): любой пользователь (включая анонимов)
        - POST (create): только авторизованные
        - PUT/PATCH/DELETE: только автор отзыва или админ
        - POST like/dislike: только авторизованные
        """
        if self.action in ["list", "retrieve"]:
            return [permissions.AllowAny()]
        elif self.action == "create":
            return [permissions.IsAuthenticated()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsOwnerOrStaff()]  # Кастомный класс прав (см. ниже)
        elif self.action in ["like", "dislike"]:
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        queryset = super().get_queryset()
        # 👇 Фильтрация по главе через ?chapter=ID
        chapter_id = self.request.query_params.get("chapter")
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        return queryset

    def perform_create(self, serializer):
        # Привязываем отзыв к текущему пользователю
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
            self.permission_denied(self.request, "Вы можете редактировать только свои отзывы.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Вы можете удалять только свои отзывы.")
        instance.delete()

    # ================= LIKE / DISLIKE ACTIONS =================
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        """Поставить лайк отзыву"""
        review = self.get_object()
        review.likes_count = models.F("likes_count") + 1
        review.save(update_fields=["likes_count"])
        # Обновляем значение после save()
        review.refresh_from_db()
        return Response({
            "detail": "Лайк поставлен",
            "likes_count": review.likes_count,
            "dislikes_count": review.dislikes_count
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def dislike(self, request, pk=None):
        """Поставить дизлайк отзыву"""
        review = self.get_object()
        review.dislikes_count = models.F("dislikes_count") + 1
        review.save(update_fields=["dislikes_count"])
        review.refresh_from_db()
        return Response({
            "detail": "Дизлайк поставлен",
            "likes_count": review.likes_count,
            "dislikes_count": review.dislikes_count
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def undo_vote(self, request, pk=None):
        """Убрать свой лайк/дизлайк (если нужно)"""
        review = self.get_object()
        # Простая логика: уменьшаем оба счётчика, если они > 0
        if review.likes_count > 0:
            review.likes_count = models.F("likes_count") - 1
        if review.dislikes_count > 0:
            review.dislikes_count = models.F("dislikes_count") - 1
        review.save(update_fields=["likes_count", "dislikes_count"])
        review.refresh_from_db()
        return Response({
            "detail": "Голос убран",
            "likes_count": review.likes_count,
            "dislikes_count": review.dislikes_count
        })


# ================= CUSTOM PERMISSION =================
class IsOwnerOrStaff(permissions.BasePermission):
    """
    Разрешает доступ только если:
    - пользователь является администратором (is_staff), ИЛИ
    - пользователь является автором объекта
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return getattr(obj, "user", None) == request.user

class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
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
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user and not self.request.user.is_staff:
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class PlaylistChapterViewSet(viewsets.ModelViewSet):
    queryset = PlaylistChapter.objects.select_related("playlist", "chapter").all()
    serializer_class = PlaylistChapterSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        return self.queryset.filter(playlist__user=self.request.user)

    def perform_update(self, serializer):
        if (
            serializer.instance.playlist.user != self.request.user
            and not self.request.user.is_staff
        ):
            self.permission_denied(self.request, "Доступ запрещен.")
        serializer.save()

    def perform_destroy(self, instance):
        if (
            instance.playlist.user != self.request.user
            and not self.request.user.is_staff
        ):
            self.permission_denied(self.request, "Доступ запрещен.")
        instance.delete()


class ViewHistoryViewSet(viewsets.ModelViewSet):
    queryset = ViewHistory.objects.select_related("user", "chapter").all()
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
        if (
            serializer.instance.user != self.request.user
            and not self.request.user.is_staff
        ):
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

    html = render_to_string(
        "cinema/pdf/subscription_receipt.html",
        {
            "subscription": subscription,
            "user": subscription.user,
        },
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="subscription_{subscription.id}_receipt.pdf"'
    )

    weasyprint.HTML(string=html).write_pdf(response)
    return response


from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from django.core.cache import cache
from .models import CompanySettings
from .serializers import CompanySettingsSerializer, PublicCompanySettingsSerializer


class CompanySettingsView(RetrieveUpdateAPIView):
    """
    🔧 View для админского редактирования настроек компании.

    GET /api/v1/admin/company-settings/ - получить настройки
    PATCH /api/v1/admin/company-settings/ - частично обновить
    PUT /api/v1/admin/company-settings/ - полностью обновить
    """

    serializer_class = CompanySettingsSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_object(self):
        """Возвращаем singleton-объект настроек"""
        return CompanySettings.get_settings()

    def perform_update(self, serializer):
        """Сохраняем с указанием кто обновил + инвалидируем кэш"""
        instance = serializer.save(updated_by=self.request.user)

        # 🔥 Инвалидируем кэш публичных настроек
        cache.delete("public_company_settings")

        return instance


class PublicCompanySettingsView(APIView):
    """
    🌐 Публичный View для получения настроек (используется в футере).

    GET /api/v1/company-settings/ - получить настройки (без авторизации)
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """Получить настройки с кэшированием"""
        cache_key = "public_company_settings"
        settings_data = cache.get(cache_key)

        if settings_data is None:
            settings = CompanySettings.get_settings()
            serializer = PublicCompanySettingsSerializer(settings)
            settings_data = serializer.data

            # Кэшируем на 1 час
            cache.set(cache_key, settings_data, 3600)

        return Response(settings_data, status=status.HTTP_200_OK)



# cinema/views/misc.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def sync_status(request):
    """
    Health-check эндпоинт для мониторинга.
    GET /api/v1/sync/
    """
    from django.db import connection
    
    # Проверка подключения к БД
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return JsonResponse({
        "service": "online_cinema",
        "version": "1.0.0",
        "database": db_status,
        "environment": settings.DEBUG and "development" or "production",
    }, status=200)