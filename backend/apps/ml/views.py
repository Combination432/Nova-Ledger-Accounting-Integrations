"""
API views for ML app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import AnomalyDetection, FinancialForecast
from .serializers import AnomalyDetectionSerializer, FinancialForecastSerializer


class AnomalyDetectionViewSet(viewsets.ModelViewSet):
    serializer_class = AnomalyDetectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['anomaly_type', 'severity', 'status']
    ordering = ['-detected_at']

    def get_queryset(self):
        return AnomalyDetection.objects.filter(
            organization=self.request.user.organization
        )

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Review and resolve an anomaly."""
        anomaly = self.get_object()
        status_val = request.data.get('status')
        notes = request.data.get('resolution_notes', '')
        
        from django.utils import timezone
        anomaly.status = status_val
        anomaly.resolution_notes = notes
        anomaly.reviewed_by = request.user
        anomaly.reviewed_at = timezone.now()
        anomaly.save()
        
        return Response(AnomalyDetectionSerializer(anomaly).data)


class FinancialForecastViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FinancialForecastSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['forecast_type', 'scenario_name']
    ordering = ['forecast_date']

    def get_queryset(self):
        return FinancialForecast.objects.filter(
            organization=self.request.user.organization
        )
