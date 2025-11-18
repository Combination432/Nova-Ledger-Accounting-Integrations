"""
Tests for inventory services - Moving Average Cost calculation.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from apps.accounts.models import Organization, ChartOfAccounts
from apps.inventory.models import InventoryItem, InventoryLocation
from apps.inventory.services import MovingAverageCostCalculator


class MovingAverageCostTest(TestCase):
    """Test MAC calculation - critical for accurate COGS."""

    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Company",
            fiscal_year_end=timezone.now().date()
        )

        self.inventory_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="1200",
            account_name="Inventory Asset",
            account_type="asset",
            account_subtype="inventory"
        )

        self.cogs_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="5000",
            account_name="Cost of Goods Sold",
            account_type="cogs",
            account_subtype="product_costs"
        )

        self.item = InventoryItem.objects.create(
            organization=self.org,
            sku="WIDGET-001",
            name="Test Widget",
            costing_method="average",
            current_average_cost=Decimal('10.00'),
            total_quantity_on_hand=Decimal('100'),
            inventory_asset_account=self.inventory_account,
            cogs_account=self.cogs_account
        )

        self.location = InventoryLocation.objects.create(
            organization=self.org,
            name="Main Warehouse",
            location_type="warehouse",
            is_default=True
        )

    def test_mac_calculation_basic(self):
        """Test basic MAC calculation."""
        calculator = MovingAverageCostCalculator()

        # Initial: 100 units @ $10 = $1,000
        # Receive: 50 units @ $12 = $600
        # New MAC should be: $1,600 / 150 = $10.67

        new_cost = calculator.calculate_new_average_cost(
            self.item,
            Decimal('50'),
            Decimal('12.00')
        )

        expected_cost = Decimal('10.67')
        self.assertAlmostEqual(new_cost, expected_cost, places=2)

    def test_receive_inventory_updates_mac(self):
        """Test that receiving inventory updates MAC correctly."""
        calculator = MovingAverageCostCalculator()

        initial_qty = self.item.total_quantity_on_hand
        initial_cost = self.item.current_average_cost

        # Receive 50 units @ $12
        calculator.receive_inventory(
            self.item,
            Decimal('50'),
            Decimal('12.00'),
            self.location
        )

        # Refresh from database
        self.item.refresh_from_db()

        # Check quantity updated
        self.assertEqual(self.item.total_quantity_on_hand, initial_qty + Decimal('50'))

        # Check MAC updated
        expected_mac = ((initial_qty * initial_cost) + (Decimal('50') * Decimal('12'))) / (initial_qty + Decimal('50'))
        self.assertAlmostEqual(self.item.current_average_cost, expected_mac, places=2)

    def test_sell_inventory_uses_current_mac(self):
        """Test that selling inventory uses current MAC for COGS."""
        calculator = MovingAverageCostCalculator()

        current_mac = self.item.current_average_cost

        # Sell 25 units
        inv_txn, unit_cost, total_cogs = calculator.sell_inventory(
            self.item,
            Decimal('25'),
            self.location
        )

        # COGS should be at current MAC
        self.assertEqual(unit_cost, current_mac)
        self.assertEqual(total_cogs, Decimal('25') * current_mac)

        # Quantity should decrease
        self.item.refresh_from_db()
        self.assertEqual(self.item.total_quantity_on_hand, Decimal('75'))

    def test_landed_cost_included_in_mac(self):
        """Test that landed costs are included in MAC calculation."""
        calculator = MovingAverageCostCalculator()

        # Receive with landed costs
        base_cost = Decimal('10.00')
        landed_cost_per_unit = Decimal('2.00')  # $2 freight per unit

        calculator.receive_inventory(
            self.item,
            Decimal('100'),
            base_cost,
            self.location,
            landed_cost_per_unit=landed_cost_per_unit
        )

        self.item.refresh_from_db()

        # New MAC should include landed costs
        # Initial: 100 @ $10 = $1,000
        # New: 100 @ $12 ($10 base + $2 landed) = $1,200
        # Total: 200 units @ $11 average
        expected_mac = Decimal('11.00')
        self.assertAlmostEqual(self.item.current_average_cost, expected_mac, places=2)
