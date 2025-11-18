"""
Tests for reporting services - Channel Profitability and Product Profitability.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta, date
from apps.accounts.models import Organization, ChartOfAccounts, SalesChannel
from apps.transactions.models import Transaction, Fee, TransactionLineItem
from apps.inventory.models import InventoryItem
from apps.reporting.services import ProfitabilityCalculator
from apps.reporting.models import ChannelProfitability, ProductProfitability


class ChannelProfitabilityTest(TestCase):
    """Test channel profitability calculation - key differentiator."""

    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Company",
            fiscal_year_end=timezone.now().date()
        )

        # Create accounts
        self.inventory_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="1200",
            account_name="Inventory",
            account_type="asset",
            account_subtype="inventory"
        )

        self.cogs_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="5000",
            account_name="COGS",
            account_type="cogs",
            account_subtype="product_costs"
        )

        self.revenue_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="4000",
            account_name="Sales Revenue",
            account_type="revenue",
            account_subtype="product_sales"
        )

        # Create sales channel
        self.channel = SalesChannel.objects.create(
            organization=self.org,
            name="Shopify Store",
            channel_type="shopify",
            is_active=True
        )

        # Create inventory item
        self.item = InventoryItem.objects.create(
            organization=self.org,
            sku="TEST-001",
            name="Test Product",
            costing_method="average",
            current_average_cost=Decimal('20.00'),
            inventory_asset_account=self.inventory_account,
            cogs_account=self.cogs_account
        )

    def test_channel_profitability_calculation(self):
        """Test comprehensive channel P&L calculation."""
        calculator = ProfitabilityCalculator(self.org)

        # Create 3 sales transactions
        for i in range(3):
            txn = Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=timezone.now().date(),
                gross_amount=Decimal('100.00'),
                net_amount=Decimal('95.00')
            )

            # Add line item with COGS
            TransactionLineItem.objects.create(
                transaction=txn,
                inventory_item=self.item,
                quantity=Decimal('1'),
                unit_price=Decimal('100.00'),
                total_amount=Decimal('100.00'),
                unit_cost=Decimal('20.00'),  # COGS
                total_cogs=Decimal('20.00')
            )

            # Add payment processing fee
            Fee.objects.create(
                transaction=txn,
                fee_type="payment_processing",
                fee_category="platform_fee",
                amount=Decimal('3.00'),
                fee_percentage=Decimal('3.00')
            )

            # Add platform fee
            Fee.objects.create(
                transaction=txn,
                fee_type="platform_fee",
                fee_category="platform_fee",
                amount=Decimal('2.00'),
                fee_percentage=Decimal('2.00')
            )

        # Calculate profitability
        period_start = timezone.now().date()
        period_end = timezone.now().date()

        profitability = calculator.calculate_channel_profitability(
            sales_channel=self.channel,
            period_start=period_start,
            period_end=period_end
        )

        # Verify calculations
        # Gross Sales: 3 * $100 = $300
        self.assertEqual(profitability.gross_sales, Decimal('300.00'))

        # Refunds: $0 (none created)
        self.assertEqual(profitability.refunds, Decimal('0.00'))

        # Net Sales: $300
        self.assertEqual(profitability.net_sales, Decimal('300.00'))

        # COGS: 3 * $20 = $60
        self.assertEqual(profitability.total_cogs, Decimal('60.00'))

        # Gross Profit: $300 - $60 = $240
        self.assertEqual(profitability.gross_profit, Decimal('240.00'))

        # Gross Margin: 240/300 = 80%
        self.assertEqual(profitability.gross_margin_percent, Decimal('80.00'))

        # Payment Fees: 3 * $3 = $9
        self.assertEqual(profitability.payment_processing_fees, Decimal('9.00'))

        # Platform Fees: 3 * $2 = $6
        self.assertEqual(profitability.platform_fees, Decimal('6.00'))

        # Total Fees: $15
        self.assertEqual(profitability.total_fees, Decimal('15.00'))

        # Net Profit: $240 - $15 = $225
        self.assertEqual(profitability.net_profit, Decimal('225.00'))

        # Net Margin: 225/300 = 75%
        self.assertEqual(profitability.net_margin_percent, Decimal('75.00'))

    def test_channel_profitability_with_refunds(self):
        """Test P&L calculation with refunds."""
        calculator = ProfitabilityCalculator(self.org)

        # Create sale
        sale = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('97.00')
        )

        # Create refund
        refund = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="refund",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('-50.00'),
            net_amount=Decimal('-48.50')
        )

        # Calculate profitability
        profitability = calculator.calculate_channel_profitability(
            sales_channel=self.channel,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )

        # Gross Sales: $100
        self.assertEqual(profitability.gross_sales, Decimal('100.00'))

        # Refunds: $50
        self.assertEqual(profitability.refunds, Decimal('50.00'))

        # Net Sales: $100 - $50 = $50
        self.assertEqual(profitability.net_sales, Decimal('50.00'))

    def test_multiple_channels_separate_profitability(self):
        """Test that profitability is correctly separated by channel."""
        calculator = ProfitabilityCalculator(self.org)

        # Create second channel
        channel2 = SalesChannel.objects.create(
            organization=self.org,
            name="Amazon Store",
            channel_type="amazon",
            is_active=True
        )

        # Create transaction on first channel
        Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('97.00')
        )

        # Create transaction on second channel
        Transaction.objects.create(
            organization=self.org,
            sales_channel=channel2,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('200.00'),
            net_amount=Decimal('194.00')
        )

        # Calculate profitability for first channel
        prof1 = calculator.calculate_channel_profitability(
            sales_channel=self.channel,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )

        # Calculate profitability for second channel
        prof2 = calculator.calculate_channel_profitability(
            sales_channel=channel2,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )

        # Verify separate calculations
        self.assertEqual(prof1.gross_sales, Decimal('100.00'))
        self.assertEqual(prof2.gross_sales, Decimal('200.00'))
        self.assertEqual(prof1.sales_channel, self.channel)
        self.assertEqual(prof2.sales_channel, channel2)


class ProductProfitabilityTest(TestCase):
    """Test product/SKU profitability calculation."""

    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Company",
            fiscal_year_end=timezone.now().date()
        )

        # Create accounts
        self.inventory_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="1200",
            account_name="Inventory",
            account_type="asset",
            account_subtype="inventory"
        )

        self.cogs_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="5000",
            account_name="COGS",
            account_type="cogs",
            account_subtype="product_costs"
        )

        # Create inventory items
        self.item = InventoryItem.objects.create(
            organization=self.org,
            sku="WIDGET-001",
            name="Premium Widget",
            costing_method="average",
            current_average_cost=Decimal('25.00'),
            inventory_asset_account=self.inventory_account,
            cogs_account=self.cogs_account
        )

        self.channel = SalesChannel.objects.create(
            organization=self.org,
            name="Test Store",
            channel_type="shopify",
            is_active=True
        )

    def test_product_profitability_calculation(self):
        """Test SKU-level profitability calculation."""
        calculator = ProfitabilityCalculator(self.org)

        # Create sales with this product
        for i in range(5):
            txn = Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=timezone.now().date(),
                gross_amount=Decimal('50.00'),
                net_amount=Decimal('48.50')
            )

            TransactionLineItem.objects.create(
                transaction=txn,
                inventory_item=self.item,
                quantity=Decimal('1'),
                unit_price=Decimal('50.00'),
                total_amount=Decimal('50.00'),
                unit_cost=Decimal('25.00'),
                total_cogs=Decimal('25.00')
            )

        # Calculate product profitability
        profitability = calculator.calculate_product_profitability(
            inventory_item=self.item,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )

        # Units Sold: 5
        self.assertEqual(profitability.units_sold, Decimal('5'))

        # Total Revenue: 5 * $50 = $250
        self.assertEqual(profitability.total_revenue, Decimal('250.00'))

        # Total COGS: 5 * $25 = $125
        self.assertEqual(profitability.total_cogs, Decimal('125.00'))

        # Gross Profit: $250 - $125 = $125
        self.assertEqual(profitability.gross_profit, Decimal('125.00'))

        # Margin: 125/250 = 50%
        self.assertEqual(profitability.margin_percent, Decimal('50.00'))
