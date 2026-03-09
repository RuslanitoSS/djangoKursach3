from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FanClubViewSet, FanClubMembershipViewSet, FanClubApplicationAttachmentViewSet

router = DefaultRouter()
router.register(r'clubs', FanClubViewSet, basename='fan_club')
router.register(r'memberships', FanClubMembershipViewSet, basename='membership')
router.register(r'attachments', FanClubApplicationAttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
]