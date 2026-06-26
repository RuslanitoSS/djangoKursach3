from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    FanClubViewSet,
    FanClubMembershipViewSet,
    FanClubApplicationAttachmentViewSet,
)

# ================= ROUTER =================
router = DefaultRouter()

# Базовый префикс пустой — он уже задан в cinema/urls.py как 'fan-clubs/'
router.register(r'', FanClubViewSet, basename='fanclub')
router.register(r'memberships', FanClubMembershipViewSet, basename='membership')
router.register(r'memberships', FanClubMembershipViewSet, basename='fanclubmembership')
router.register(r'attachments', FanClubApplicationAttachmentViewSet, basename='attachment')

urlpatterns = [
    path('', include(router.urls)),
]