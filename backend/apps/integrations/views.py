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
        """
        Trigger manual sync for this integration.

        Query params:
        - force_full_sync: (bool) If true, perform full sync instead of incremental
        - async: (bool) If true, queue sync task and return immediately (default: false)
        """
        integration = self.get_object()
        force_full_sync = request.data.get('force_full_sync', False)
        async_sync = request.data.get('async', False)

        if not integration.is_active:
            return Response(
                {'error': 'Integration is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if async_sync:
                # Queue the sync task
                from .tasks import sync_integration_transactions
                task = sync_integration_transactions.delay(str(integration.id), force_full_sync)

                return Response({
                    'status': 'queued',
                    'task_id': task.id,
                    'message': 'Sync task queued successfully'
                }, status=status.HTTP_202_ACCEPTED)
            else:
                # Run sync synchronously
                from .sync_engine import SyncEngine
                engine = SyncEngine(integration)
                result = engine.sync_transactions(force_full_sync=force_full_sync)

                return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sync_status(self, request, pk=None):
        """
        Get current sync status for this integration.
        Returns information about last sync, next scheduled sync, and statistics.
        """
        integration = self.get_object()

        try:
            from .sync_engine import SyncEngine
            engine = SyncEngine(integration)
            status_info = engine.get_sync_status()

            return Response(status_info, status=status.HTTP_200_OK)

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
