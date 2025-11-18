from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RevenueContractViewSet, SubscriptionMetricViewSet,
    CustomerCohortViewSet
)

router = DefaultRouter()
router.register(r'contracts', RevenueContractViewSet, basename='revenuecontract')
router.register(r'saas-metrics', SubscriptionMetricViewSet, basename='subscriptionmetric')
router.register(r'cohorts', CustomerCohortViewSet, basename='customercohort')

urlpatterns = [
    path('', include(router.urls)),
]
