from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import sync_status
from . import views
from .views import (
    UserViewSet,
    UserPaymentMethodViewSet,
    SubscriptionViewSet,
    UserSubscriptionViewSet,
    GenreViewSet,
    FranchiseViewSet,
    ChapterViewSet,
    EpisodeViewSet,
    PersonViewSet,
    ChapterPersonRoleViewSet,
    CommentViewSet,
    ReviewViewSet,
    RatingViewSet,
    PlaylistViewSet,
    ViewHistoryViewSet,
    PlaylistChapterViewSet,
    subscription_receipt_pdf,
)

# Auth-вьюхи
from .views import (
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    RegisterView,
    LogoutView,
    MeView,
)

# ================= ROUTER =================
router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"payment-methods", UserPaymentMethodViewSet, basename="paymentmethod")
router.register(r"subscriptions", SubscriptionViewSet, basename="subscription")
router.register(
    r"user-subscriptions", UserSubscriptionViewSet, basename="usersubscription"
)
router.register(r"genres", GenreViewSet, basename="genre")
router.register(r"franchises", FranchiseViewSet, basename="franchise")
router.register(r"chapters", ChapterViewSet, basename="chapter")
router.register(r"episodes", EpisodeViewSet, basename="episode")
router.register(r"people", PersonViewSet, basename="person")
router.register(
    r"chapter-person-roles", ChapterPersonRoleViewSet, basename="chapterpersonrole"
)
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"ratings", RatingViewSet, basename="rating")
router.register(r"playlists", PlaylistViewSet, basename="playlist")
router.register(
    r"playlist-chapters", PlaylistChapterViewSet, basename="playlistchapter"
)
router.register(r"view-histories", ViewHistoryViewSet, basename="viewhistory")

urlpatterns = [
    # Основные эндпоинты API: /api/v1/users/, /api/v1/franchises/ и т.д.
    path("", include(router.urls)),
    # 👇 Fan clubs: /api/v1/fan-clubs/...
    path("fan-clubs/", include("fan_clubs.urls")),
    # ================= AUTH ENDPOINTS =================
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="auth_login"),
    path("auth/token/refresh/", CustomTokenRefreshView.as_view(), name="auth_refresh"),
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    path("auth/me/", MeView.as_view(), name="auth_me"),
    # ==================================================
    # PDF-генерация чека (админская, не REST)
    path(
        "admin/subscriptions/<int:subscription_id>/receipt.pdf/",
        subscription_receipt_pdf,
        name="subscription_receipt_pdf",
    ),
    path(
        "admin/company-settings/",
        views.CompanySettingsView.as_view(),
        name="admin-company-settings",
    ),
    path(
        "company-settings/",
        views.PublicCompanySettingsView.as_view(),
        name="public-company-settings",
    ),

    path("sync/", sync_status, name="sync-status"),
]
