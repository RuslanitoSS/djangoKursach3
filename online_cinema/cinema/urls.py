from django.urls import path, include
from rest_framework.routers import DefaultRouter
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
)

# Создание маршрутов для ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'payment-methods', UserPaymentMethodViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'user-subscriptions', UserSubscriptionViewSet)
router.register(r'genres', GenreViewSet)
router.register(r'franchises', FranchiseViewSet)
router.register(r'chapters', ChapterViewSet)
router.register(r'episodes', EpisodeViewSet)
router.register(r'people', PersonViewSet)
router.register(r'chapter-person-roles', ChapterPersonRoleViewSet)
router.register(r'comments', CommentViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'ratings', RatingViewSet)
router.register(r'playlists', PlaylistViewSet)
router.register(r'playlist-chapters', PlaylistChapterViewSet)
router.register(r'ViewHistorys', ViewHistoryViewSet)


urlpatterns = [
    path('v1/', include(router.urls)),
]
