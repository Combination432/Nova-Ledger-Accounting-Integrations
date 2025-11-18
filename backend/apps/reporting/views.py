"""
API views for reporting app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, api_view, throttle_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Avg
from apps.common.throttles import ReportingRateThrottle
from .models import ChannelProfitability, ProductProfitability, DashboardMetric
from .serializers import (
    ChannelProfitabilitySerializer, ProductProfitabilitySerializer,
    DashboardMetricSerializer
)


@api_view(['GET'])
@throttle_classes([ReportingRateThrottle])
def dashboard_metrics(request):
    """Get comprehensive dashboard metrics."""
    from datetime import datetime, timedelta
    from apps.transactions.models import Transaction
    from django.utils import timezone
    
    organization = request.user.organization
    date_range = request.GET.get('date_range', '30d')
    
    # Calculate date range
    if date_range == '7d':
        start_date = timezone.now() - timedelta(days=7)
    elif date_range == '90d':
        start_date = timezone.now() - timedelta(days=90)
    elif date_range == '12m':
        start_date = timezone.now() - timedelta(days=365)
    else:  # 30d default
        start_date = timezone.now() - timedelta(days=30)
    
    # Get transactions
    transactions = Transaction.objects.filter(
        organization=organization,
        transaction_date__gte=start_date,
        transaction_type='sale'
    )
    
    # Calculate metrics
    total_revenue = transactions.aggregate(Sum('gross_amount'))['gross_amount__sum'] or 0
    order_count = transactions.count()
    
    # Get anomalies
    from apps.ml.models import AnomalyDetection
    anomalies_count = AnomalyDetection.objects.filter(
        organization=organization,
        status='pending'
    ).count()
    
    return Response({
        'total_revenue': total_revenue,
        'order_count': order_count,
        'average_order_value': total_revenue / order_count if order_count > 0 else 0,
        'anomalies_count': anomalies_count,
        'period': date_range
    })


class ChannelProfitabilityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChannelProfitabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReportingRateThrottle]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['sales_channel', 'period_type']
    ordering = ['-period_start']

    def get_queryset(self):
        return ChannelProfitability.objects.filter(
            organization=self.request.user.organization
        )


class ProductProfitabilityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductProfitabilitySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReportingRateThrottle]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['inventory_item', 'sales_channel', 'period_type']
    ordering = ['-period_start']

    def get_queryset(self):
        return ProductProfitability.objects.filter(
            organization=self.request.user.organization
        )


class DashboardMetricViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DashboardMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ReportingRateThrottle]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['metric_category', 'metric_name', 'period_type']
    ordering = ['-period_date']

    def get_queryset(self):
        return DashboardMetric.objects.filter(
            organization=self.request.user.organization
        )
