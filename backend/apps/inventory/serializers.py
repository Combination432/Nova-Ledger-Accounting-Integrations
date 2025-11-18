"""
Serializers for inventory app.
"""
from rest_framework import serializers
from .models import (
    InventoryItem, InventoryBalance, InventoryLocation,
    InventoryTransaction, LandedCost, LandedCostAllocation,
    PurchaseOrder, PurchaseOrderLine
)


class InventoryLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryLocation
        fields = '__all__'


class InventoryBalanceSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = InventoryBalance
        fields = '__all__'


class InventoryItemSerializer(serializers.ModelSerializer):
    balances = InventoryBalanceSerializer(many=True, read_only=True)
    
    class Meta:
        model = InventoryItem
        fields = '__all__'


class InventoryTransactionSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)
    
    class Meta:
        model = InventoryTransaction
        fields = '__all__'


class LandedCostAllocationSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    
    class Meta:
        model = LandedCostAllocation
        fields = '__all__'


class LandedCostSerializer(serializers.ModelSerializer):
    allocations = LandedCostAllocationSerializer(many=True, read_only=True)
    
    class Meta:
        model = LandedCost
        fields = '__all__'


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    item_sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    
    class Meta:
        model = PurchaseOrderLine
        fields = '__all__'


class PurchaseOrderSerializer(serializers.ModelSerializer):
    line_items = PurchaseOrderLineSerializer(many=True, read_only=True)
    landed_costs = LandedCostSerializer(many=True, read_only=True)
    
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
