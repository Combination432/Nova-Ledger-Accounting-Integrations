from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AnomalyDetectionViewSet, FinancialForecastViewSet

router = DefaultRouter()
router.register(r'anomalies', AnomalyDetectionViewSet, basename='anomalydetection')
router.register(r'forecasts', FinancialForecastViewSet, basename='financialforecast')

urlpatterns = [
    path('', include(router.urls)),
]
