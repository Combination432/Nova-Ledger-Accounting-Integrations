"""
API views for revenue recognition app.
"""
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import RevenueContract, SubscriptionMetric, CustomerCohort
from .serializers import (
    RevenueContractSerializer, SubscriptionMetricSerializer,
    CustomerCohortSerializer
)


class RevenueContractViewSet(viewsets.ModelViewSet):
    serializer_class = RevenueContractSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'customer_id']
    search_fields = ['contract_number', 'customer_name']
    ordering = ['-contract_date']

    def get_queryset(self):
        return RevenueContract.objects.filter(
            organization=self.request.user.organization
        ).prefetch_related('schedules')

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class SubscriptionMetricViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubscriptionMetricSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['metric_type', 'product_category', 'acquisition_channel']
    ordering = ['-metric_date']

    def get_queryset(self):
        return SubscriptionMetric.objects.filter(
            organization=self.request.user.organization
        )


class CustomerCohortViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerCohortSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['acquisition_channel', 'product_category']
    ordering = ['-cohort_date']

    def get_queryset(self):
        return CustomerCohort.objects.filter(
            organization=self.request.user.organization
        )
