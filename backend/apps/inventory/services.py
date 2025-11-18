"""
Core business logic services for inventory management.
These are the critical calculation engines that make Nova Ledger's inventory tracking work.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from .models import (
    InventoryItem, InventoryBalance, InventoryTransaction,
    LandedCost, LandedCostAllocation, PurchaseOrder
)
import logging

logger = logging.getLogger(__name__)


class MovingAverageCostCalculator:
    """
    Calculate Moving Average Cost (MAC) for inventory items.
    This is a KEY DIFFERENTIATOR for Nova Ledger.
    """

    @staticmethod
    def calculate_new_average_cost(item: InventoryItem, new_qty: Decimal, new_cost: Decimal) -> Decimal:
        """
        Calculate new moving average cost when inventory is received.

        Formula:
        New MAC = (Old Qty × Old Cost + New Qty × New Cost) / (Old Qty + New Qty)

        Args:
            item: The inventory item
            new_qty: Quantity being received
            new_cost: Unit cost of new inventory

        Returns:
            New average cost
        """
        if new_qty <= 0:
            return item.current_average_cost

        old_qty = item.total_quantity_on_hand
        old_cost = item.current_average_cost

        # Calculate weighted average
        old_value = old_qty * old_cost
        new_value = new_qty * new_cost
        total_qty = old_qty + new_qty

        if total_qty == 0:
            return new_cost

        new_avg_cost = (old_value + new_value) / total_qty

        logger.info(
            f"MAC Calculation for {item.sku}: "
            f"Old: {old_qty} @ ${old_cost} = ${old_value}, "
            f"New: {new_qty} @ ${new_cost} = ${new_value}, "
            f"Result: {total_qty} @ ${new_avg_cost}"
        )

        return new_avg_cost

    @staticmethod
    @transaction.atomic
    def receive_inventory(
        item: InventoryItem,
        quantity: Decimal,
        unit_cost: Decimal,
        location,
        purchase_order=None,
        landed_cost_per_unit: Decimal = Decimal('0')
    ):
        """
        Receive inventory and update moving average cost.

        Args:
            item: Inventory item being received
            quantity: Quantity received
            unit_cost: Base unit cost
            location: Inventory location
            purchase_order: Optional PO reference
            landed_cost_per_unit: Additional landed costs per unit

        Returns:
            InventoryTransaction object
        """
        # Calculate total cost including landed costs
        total_unit_cost = unit_cost + landed_cost_per_unit

        # Calculate new moving average cost
        new_avg_cost = MovingAverageCostCalculator.calculate_new_average_cost(
            item, quantity, total_unit_cost
        )

        # Update item
        item.current_average_cost = new_avg_cost
        item.total_quantity_on_hand += quantity
        item.total_value = item.total_quantity_on_hand * new_avg_cost
        item.save()

        # Update or create balance for location
        balance, created = InventoryBalance.objects.get_or_create(
            inventory_item=item,
            location=location,
            defaults={
                'quantity_on_hand': Decimal('0'),
                'average_cost': new_avg_cost
            }
        )

        balance.quantity_on_hand += quantity
        balance.quantity_available += quantity
        balance.average_cost = new_avg_cost
        balance.total_value = balance.quantity_on_hand * new_avg_cost
        balance.save()

        # Create inventory transaction
        inv_txn = InventoryTransaction.objects.create(
            organization=item.organization,
            inventory_item=item,
            location=location,
            transaction_type='receipt',
            transaction_date=timezone.now(),
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            landed_cost_per_unit=landed_cost_per_unit,
            total_landed_cost=quantity * landed_cost_per_unit,
            purchase_order=purchase_order
        )

        logger.info(
            f"Received {quantity} of {item.sku} at ${total_unit_cost}/unit. "
            f"New MAC: ${new_avg_cost}, Total Qty: {item.total_quantity_on_hand}"
        )

        return inv_txn

    @staticmethod
    @transaction.atomic
    def sell_inventory(item: InventoryItem, quantity: Decimal, location):
        """
        Sell/ship inventory and calculate COGS using current average cost.

        Args:
            item: Inventory item being sold
            quantity: Quantity sold
            location: Location shipping from

        Returns:
            tuple: (InventoryTransaction, unit_cost, total_cogs)
        """
        if quantity > item.total_quantity_on_hand:
            raise ValueError(
                f"Insufficient inventory for {item.sku}. "
                f"Available: {item.total_quantity_on_hand}, Requested: {quantity}"
            )

        # COGS is calculated at current moving average cost
        unit_cost = item.current_average_cost
        total_cogs = quantity * unit_cost

        # Update item quantity (cost stays the same in MAC)
        item.total_quantity_on_hand -= quantity
        item.total_value = item.total_quantity_on_hand * item.current_average_cost
        item.save()

        # Update balance
        balance = InventoryBalance.objects.get(
            inventory_item=item,
            location=location
        )
        balance.quantity_on_hand -= quantity
        balance.quantity_available -= quantity
        balance.total_value = balance.quantity_on_hand * balance.average_cost
        balance.save()

        # Create inventory transaction (negative quantity)
        inv_txn = InventoryTransaction.objects.create(
            organization=item.organization,
            inventory_item=item,
            location=location,
            transaction_type='sale',
            transaction_date=timezone.now(),
            quantity=-quantity,  # Negative for outbound
            unit_cost=unit_cost,
            total_cost=-total_cogs
        )

        logger.info(
            f"Sold {quantity} of {item.sku} at ${unit_cost}/unit COGS. "
            f"Remaining: {item.total_quantity_on_hand}"
        )

        return inv_txn, unit_cost, total_cogs


class LandedCostAllocator:
    """
    Allocate landed costs (freight, duties, insurance) to inventory items.
    This is a KEY DIFFERENTIATOR for Nova Ledger - true COGS calculation.
    """

    @staticmethod
    @transaction.atomic
    def allocate_by_value(landed_cost: LandedCost) -> list:
        """
        Allocate landed cost to PO line items proportionally by value.

        Args:
            landed_cost: LandedCost object to allocate

        Returns:
            List of LandedCostAllocation objects created
        """
        purchase_order = landed_cost.purchase_order
        line_items = purchase_order.line_items.all()

        if not line_items:
            raise ValueError("Purchase order has no line items to allocate to")

        # Calculate total PO value
        total_po_value = sum(line.total_cost for line in line_items)

        if total_po_value == 0:
            raise ValueError("Purchase order total value is zero")

        allocations = []

        for line in line_items:
            # Calculate allocation percentage based on value
            allocation_percentage = line.total_cost / total_po_value

            # Calculate allocated amount
            allocated_amount = landed_cost.total_amount * allocation_percentage

            # Calculate per-unit landed cost
            allocated_per_unit = allocated_amount / line.quantity_ordered if line.quantity_ordered > 0 else Decimal('0')

            # Create allocation
            allocation = LandedCostAllocation.objects.create(
                landed_cost=landed_cost,
                inventory_item=line.inventory_item,
                allocation_basis=line.total_cost,
                allocation_percentage=allocation_percentage,
                allocated_amount=allocated_amount,
                allocated_per_unit=allocated_per_unit
            )

            allocations.append(allocation)

            logger.info(
                f"Allocated ${allocated_amount} ({allocation_percentage:.2%}) "
                f"of {landed_cost.cost_type} to {line.inventory_item.sku} "
                f"(${allocated_per_unit}/unit)"
            )

        # Mark landed cost as allocated
        landed_cost.is_allocated = True
        landed_cost.allocated_date = timezone.now()
        landed_cost.save()

        return allocations

    @staticmethod
    @transaction.atomic
    def allocate_by_quantity(landed_cost: LandedCost) -> list:
        """Allocate landed cost proportionally by quantity."""
        purchase_order = landed_cost.purchase_order
        line_items = purchase_order.line_items.all()

        total_qty = sum(line.quantity_ordered for line in line_items)

        if total_qty == 0:
            raise ValueError("Purchase order total quantity is zero")

        allocations = []

        for line in line_items:
            allocation_percentage = line.quantity_ordered / total_qty
            allocated_amount = landed_cost.total_amount * allocation_percentage
            allocated_per_unit = allocated_amount / line.quantity_ordered

            allocation = LandedCostAllocation.objects.create(
                landed_cost=landed_cost,
                inventory_item=line.inventory_item,
                allocation_basis=line.quantity_ordered,
                allocation_percentage=allocation_percentage,
                allocated_amount=allocated_amount,
                allocated_per_unit=allocated_per_unit
            )

            allocations.append(allocation)

        landed_cost.is_allocated = True
        landed_cost.allocated_date = timezone.now()
        landed_cost.save()

        return allocations

    @staticmethod
    @transaction.atomic
    def allocate_by_weight(landed_cost: LandedCost, weights: dict) -> list:
        """
        Allocate landed cost proportionally by weight.

        Args:
            landed_cost: LandedCost object
            weights: Dict mapping inventory_item_id to weight

        Returns:
            List of allocations
        """
        purchase_order = landed_cost.purchase_order
        line_items = purchase_order.line_items.all()

        total_weight = sum(weights.get(str(line.inventory_item.id), Decimal('0')) for line in line_items)

        if total_weight == 0:
            raise ValueError("Total weight is zero")

        allocations = []

        for line in line_items:
            weight = weights.get(str(line.inventory_item.id), Decimal('0'))
            allocation_percentage = weight / total_weight
            allocated_amount = landed_cost.total_amount * allocation_percentage
            allocated_per_unit = allocated_amount / line.quantity_ordered if line.quantity_ordered > 0 else Decimal('0')

            allocation = LandedCostAllocation.objects.create(
                landed_cost=landed_cost,
                inventory_item=line.inventory_item,
                allocation_basis=weight,
                allocation_percentage=allocation_percentage,
                allocated_amount=allocated_amount,
                allocated_per_unit=allocated_per_unit
            )

            allocations.append(allocation)

        landed_cost.is_allocated = True
        landed_cost.allocated_date = timezone.now()
        landed_cost.save()

        return allocations
