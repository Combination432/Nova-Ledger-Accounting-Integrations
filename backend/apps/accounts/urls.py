"""
URL configuration for accounts app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OrganizationViewSet,
    ChartOfAccountsViewSet,
    SalesChannelViewSet
)

router = DefaultRouter()
router.register(r'organizations', OrganizationViewSet, basename='organization')
router.register(r'chart-of-accounts', ChartOfAccountsViewSet, basename='chartofaccounts')
router.register(r'sales-channels', SalesChannelViewSet, basename='saleschannel')

urlpatterns = [
    path('', include(router.urls)),
]
