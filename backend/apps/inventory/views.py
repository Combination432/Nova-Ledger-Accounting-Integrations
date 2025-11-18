"""
API views for inventory app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import InventoryItem, InventoryLocation, InventoryTransaction, PurchaseOrder
from .serializers import (
    InventoryItemSerializer, InventoryLocationSerializer,
    InventoryTransactionSerializer, PurchaseOrderSerializer
)


class InventoryItemViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['track_inventory', 'is_active', 'category', 'costing_method']
    search_fields = ['sku', 'name', 'description']
    ordering_fields = ['sku', 'name', 'total_quantity_on_hand', 'current_average_cost']
    ordering = ['sku']

    def get_queryset(self):
        return InventoryItem.objects.filter(
            organization=self.request.user.organization
        ).prefetch_related('balances')

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def adjust_quantity(self, request, pk=None):
        """Adjust inventory quantity."""
        item = self.get_object()
        quantity = request.data.get('quantity')
        location_id = request.data.get('location_id')
        notes = request.data.get('notes', '')
        
        from decimal import Decimal
        from django.utils import timezone
        
        # Create adjustment transaction
        InventoryTransaction.objects.create(
            organization=self.request.user.organization,
            inventory_item=item,
            location_id=location_id,
            transaction_type='adjustment',
            transaction_date=timezone.now(),
            quantity=Decimal(quantity),
            unit_cost=item.current_average_cost,
            total_cost=Decimal(quantity) * item.current_average_cost,
            notes=notes
        )
        
        # Update item quantity
        item.total_quantity_on_hand += Decimal(quantity)
        item.save()
        
        return Response({'status': 'adjusted', 'new_quantity': item.total_quantity_on_hand})


class InventoryLocationViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryLocationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['location_type', 'is_active']
    search_fields = ['name', 'city', 'state']

    def get_queryset(self):
        return InventoryLocation.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class InventoryTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'inventory_item', 'location']
    ordering = ['-transaction_date']

    def get_queryset(self):
        return InventoryTransaction.objects.filter(
            organization=self.request.user.organization
        )


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'vendor_name']
    search_fields = ['po_number', 'vendor_name']
    ordering = ['-po_date']

    def get_queryset(self):
        return PurchaseOrder.objects.filter(
            organization=self.request.user.organization
        ).prefetch_related('line_items', 'landed_costs')

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        """Receive inventory from purchase order."""
        po = self.get_object()
        
        if po.status == 'received':
            return Response(
                {'error': 'PO already received'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark as received
        from django.utils import timezone
        po.status = 'received'
        po.received_date = timezone.now().date()
        po.save()
        
        # Create inventory transactions for each line
        for line in po.line_items.all():
            InventoryTransaction.objects.create(
                organization=self.request.user.organization,
                inventory_item=line.inventory_item,
                location=po.destination_location,
                transaction_type='receipt',
                transaction_date=timezone.now(),
                quantity=line.quantity_ordered,
                unit_cost=line.unit_cost,
                total_cost=line.total_cost,
                purchase_order=po,
                reference_number=po.po_number
            )
            
            # Update item quantity
            item = line.inventory_item
            item.total_quantity_on_hand += line.quantity_ordered
            item.save()
        
        return Response({'status': 'received'})
