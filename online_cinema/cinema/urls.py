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
    # 👇 Импортируем новую функцию для PDF
    subscription_receipt_pdf,
)

# Создание маршрутов для ViewSets
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'payment-methods', UserPaymentMethodViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'user-subscriptions', UserSubscriptionViewSet, basename='usersubscription')
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
router.register(r'view-histories', ViewHistoryViewSet)  # 👇 исправил на нижний регистр с дефисом


urlpatterns = [
    path('v1/', include(router.urls)),
    path('v1/clubs/', include('fan_clubs.urls')),
    
    # 👇 PDF-генерация (не API, а прямой файл)
    path('v1/admin/subscriptions/<int:subscription_id>/receipt.pdf/', 
         subscription_receipt_pdf, 
         name='subscription_receipt_pdf'),
]