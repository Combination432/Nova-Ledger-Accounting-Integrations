"""
API views for integrations app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Integration, SyncLog, WebhookEvent, TaxConfiguration
from .serializers import (
    IntegrationSerializer, SyncLogSerializer,
    WebhookEventSerializer, TaxConfigurationSerializer
)


class IntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['integration_type', 'is_active', 'is_connected']
    search_fields = ['name', 'integration_type']

    def get_queryset(self):
        return Integration.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """Trigger a sync for this integration."""
        integration = self.get_object()
        sync_type = request.data.get('sync_type', 'full')
        
        # Import appropriate service
        from .services import (
            ShopifyIntegrationService,
            StripeIntegrationService,
            QuickBooksIntegrationService
        )
        
        try:
            if integration.integration_type == 'shopify':
                service = ShopifyIntegrationService(integration)
                if sync_type == 'orders':
                    result = service.sync_orders()
                elif sync_type == 'inventory':
                    result = service.sync_inventory()
                else:
                    result = service.sync_orders()
                    
            elif integration.integration_type == 'stripe':
                service = StripeIntegrationService(integration)
                result = service.sync_charges()
                
            elif integration.integration_type == 'quickbooks_online':
                service = QuickBooksIntegrationService(integration)
                result = service.sync_chart_of_accounts()
            else:
                return Response(
                    {'error': 'Integration type not supported for sync'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(SyncLogSerializer(result).data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sync_logs(self, request, pk=None):
        """Get sync logs for this integration."""
        integration = self.get_object()
        logs = integration.sync_logs.order_by('-started_at')[:50]
        return Response(SyncLogSerializer(logs, many=True).data)


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'sync_type', 'integration']
    ordering = ['-started_at']

    def get_queryset(self):
        return SyncLog.objects.filter(
            integration__organization=self.request.user.organization
        )


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'event_type']
    ordering = ['-received_at']

    def get_queryset(self):
        return WebhookEvent.objects.filter(
            webhook_endpoint__integration__organization=self.request.user.organization
        )


class TaxConfigurationViewSet(viewsets.ModelViewSet):
    serializer_class = TaxConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['country', 'state_province', 'is_active', 'has_nexus']
    search_fields = ['tax_name', 'country', 'state_province']

    def get_queryset(self):
        return TaxConfiguration.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
