from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    dashboard_metrics, ChannelProfitabilityViewSet,
    ProductProfitabilityViewSet, DashboardMetricViewSet
)

router = DefaultRouter()
router.register(r'channel-profitability', ChannelProfitabilityViewSet, basename='channelprofitability')
router.register(r'product-profitability', ProductProfitabilityViewSet, basename='productprofitability')
router.register(r'dashboard-metrics-history', DashboardMetricViewSet, basename='dashboardmetric')

urlpatterns = [
    path('dashboard-metrics/', dashboard_metrics, name='dashboard-metrics'),
    path('', include(router.urls)),
]
