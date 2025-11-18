from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    IntegrationViewSet, SyncLogViewSet,
    WebhookEventViewSet, TaxConfigurationViewSet
)

router = DefaultRouter()
router.register(r'', IntegrationViewSet, basename='integration')
router.register(r'sync-logs', SyncLogViewSet, basename='synclog')
router.register(r'webhook-events', WebhookEventViewSet, basename='webhookevent')
router.register(r'tax-config', TaxConfigurationViewSet, basename='taxconfiguration')

urlpatterns = [
    path('', include(router.urls)),
]
