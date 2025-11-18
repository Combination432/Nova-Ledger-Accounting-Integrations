"""
Inventory models for Nova Ledger.
Advanced perpetual inventory tracking with landed costs - a key differentiator.
"""
from django.db import models
from apps.accounts.models import Organization, ChartOfAccounts
from decimal import Decimal
import uuid


class InventoryItem(models.Model):
    """
    Master inventory item with perpetual tracking.
    """
    COSTING_METHODS = [
        ('fifo', 'First In, First Out'),
        ('lifo', 'Last In, First Out'),
        ('average', 'Moving Average Cost'),
        ('standard', 'Standard Cost'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='inventory_items')

    # Item identification
    sku = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Product variants
    parent_product_id = models.CharField(max_length=255, blank=True)
    variant_id = models.CharField(max_length=255, blank=True)

    # Item classification
    category = models.CharField(max_length=100, blank=True)
    product_type = models.CharField(max_length=100, blank=True)
    vendor = models.CharField(max_length=255, blank=True)

    # Inventory tracking
    track_inventory = models.BooleanField(default=True)
    is_bundle = models.BooleanField(default=False)

    # Costing
    costing_method = models.CharField(max_length=20, choices=COSTING_METHODS, default='average')
    current_average_cost = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    standard_cost = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)

    # Current balances (aggregated from InventoryBalance)
    total_quantity_on_hand = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # GL accounts
    inventory_asset_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='inventory_items'
    )
    cogs_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='inventory_cogs'
    )

    # Integration IDs
    shopify_product_id = models.CharField(max_length=255, blank=True)
    shopify_variant_id = models.CharField(max_length=255, blank=True)
    amazon_asin = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_items'
        unique_together = ['organization', 'sku']

    def __str__(self):
        return f"{self.sku} - {self.name}"


class InventoryBalance(models.Model):
    """
    Inventory balances by location (warehouse, FBA, 3PL, etc.).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='balances')
    location = models.ForeignKey('InventoryLocation', on_delete=models.CASCADE)

    # Quantities
    quantity_on_hand = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    quantity_allocated = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    quantity_available = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # Valuation (at current average cost)
    total_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_cost = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_balances'
        unique_together = ['inventory_item', 'location']


class InventoryLocation(models.Model):
    """
    Storage locations for inventory (warehouses, FBA, 3PLs).
    """
    LOCATION_TYPES = [
        ('warehouse', 'Internal Warehouse'),
        ('fba', 'Amazon FBA'),
        ('3pl', 'Third-Party Logistics'),
        ('retail', 'Retail Store'),
        ('virtual', 'Virtual/Dropship'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='inventory_locations')

    name = models.CharField(max_length=255)
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPES)

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True)

    # Settings
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_locations'

    def __str__(self):
        return f"{self.name} ({self.location_type})"


class InventoryTransaction(models.Model):
    """
    Individual inventory movements (receipts, sales, adjustments, transfers).
    """
    TRANSACTION_TYPES = [
        ('receipt', 'Receipt/Purchase'),
        ('sale', 'Sale/Shipment'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
        ('return', 'Return'),
        ('cycle_count', 'Cycle Count'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='inventory_transactions')

    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    location = models.ForeignKey(InventoryLocation, on_delete=models.CASCADE)

    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_date = models.DateTimeField(db_index=True)
    reference_number = models.CharField(max_length=100, blank=True)

    # Quantity
    quantity = models.DecimalField(max_digits=15, decimal_places=3)  # Can be negative for outbound

    # Costing
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)

    # Landed costs (for receipts)
    landed_cost_per_unit = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    total_landed_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Links
    source_transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inventory_transactions'
        ordering = ['-transaction_date']


class LandedCost(models.Model):
    """
    Landed costs (freight, customs, duties) to be allocated to inventory.
    This is a KEY DIFFERENTIATOR for Nova Ledger.
    """
    COST_TYPES = [
        ('freight', 'Freight/Shipping'),
        ('customs', 'Customs Duties'),
        ('insurance', 'Insurance'),
        ('handling', 'Handling Fees'),
        ('inspection', 'Inspection Fees'),
        ('other', 'Other'),
    ]

    ALLOCATION_METHODS = [
        ('quantity', 'By Quantity'),
        ('value', 'By Value'),
        ('weight', 'By Weight'),
        ('volume', 'By Volume'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='landed_costs')

    # Cost details
    cost_type = models.CharField(max_length=20, choices=COST_TYPES)
    description = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Related purchase
    purchase_order = models.ForeignKey('PurchaseOrder', on_delete=models.CASCADE, related_name='landed_costs')

    # Allocation
    allocation_method = models.CharField(max_length=20, choices=ALLOCATION_METHODS, default='value')
    is_allocated = models.BooleanField(default=False)
    allocated_date = models.DateTimeField(null=True, blank=True)

    # GL account
    expense_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'landed_costs'


class LandedCostAllocation(models.Model):
    """
    Individual allocations of landed costs to inventory items.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    landed_cost = models.ForeignKey(LandedCost, on_delete=models.CASCADE, related_name='allocations')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)

    # Allocation basis (quantity, value, weight, etc.)
    allocation_basis = models.DecimalField(max_digits=15, decimal_places=4)
    allocation_percentage = models.DecimalField(max_digits=5, decimal_places=4)

    # Allocated amount
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    allocated_per_unit = models.DecimalField(max_digits=15, decimal_places=4)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'landed_cost_allocations'


class PurchaseOrder(models.Model):
    """
    Purchase orders for inventory receipts.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('partially_received', 'Partially Received'),
        ('received', 'Fully Received'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='purchase_orders')

    # PO details
    po_number = models.CharField(max_length=100, unique=True)
    vendor_name = models.CharField(max_length=255)
    vendor_id = models.CharField(max_length=255, blank=True)

    # Dates
    po_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)
    received_date = models.DateField(null=True, blank=True)

    # Totals
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_landed_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Shipping
    shipping_address = models.TextField(blank=True)
    destination_location = models.ForeignKey(InventoryLocation, on_delete=models.SET_NULL, null=True)

    # Notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchase_orders'
        ordering = ['-po_date']

    def __str__(self):
        return f"PO-{self.po_number}"


class PurchaseOrderLine(models.Model):
    """Line items in a purchase order."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='line_items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)

    # Ordered quantities
    quantity_ordered = models.DecimalField(max_digits=15, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=15, decimal_places=3, default=0)

    # Pricing
    unit_cost = models.DecimalField(max_digits=15, decimal_places=4)
    total_cost = models.DecimalField(max_digits=15, decimal_places=2)

    # Notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'purchase_order_lines'
