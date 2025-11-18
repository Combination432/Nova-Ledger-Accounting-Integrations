"""
Tests for analytics service.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.transactions.models import Transaction
from apps.integrations.services.analytics_service import AnalyticsService

User = get_user_model()


class AnalyticsServiceTestCase(TestCase):
    """Test cases for AnalyticsService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.organization = self.user.organization
        self.service = AnalyticsService(self.organization)

        # Create test transactions
        self.create_test_data()

    def create_test_data(self):
        """Create comprehensive test data."""
        base_date = date(2024, 1, 1)

        # Create sales transactions
        for i in range(30):
            Transaction.objects.create(
                organization=self.organization,
                transaction_type='sale',
                transaction_date=base_date + timedelta(days=i),
                gross_amount=Decimal('100.00') + Decimal(i * 10),
                net_amount=Decimal('90.00') + Decimal(i * 10),
                tax_amount=Decimal('10.00'),
                customer_name=f'Customer {i % 5}',  # 5 different customers
                source_platform='shopify',
                category='Product Sales'
            )

        # Create expense transactions
        for i in range(15):
            Transaction.objects.create(
                organization=self.organization,
                transaction_type='expense',
                transaction_date=base_date + timedelta(days=i * 2),
                gross_amount=Decimal('50.00') + Decimal(i * 5),
                net_amount=Decimal('50.00') + Decimal(i * 5),
                category='Office Expenses',
                source_platform='quickbooks'
            )

    def test_get_dashboard_kpis(self):
        """Test dashboard KPIs calculation."""
        kpis = self.service.get_dashboard_kpis(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        # Verify structure
        self.assertIn('revenue', kpis)
        self.assertIn('expenses', kpis)
        self.assertIn('profit', kpis)
        self.assertIn('transactions', kpis)

        # Verify revenue
        self.assertGreater(kpis['revenue']['current'], 0)
        self.assertIn('change_percent', kpis['revenue'])
        self.assertIn('trend', kpis['revenue'])

        # Verify profit margin
        self.assertIn('margin_percent', kpis['profit'])

    def test_get_revenue_trend_by_day(self):
        """Test revenue trend by day."""
        trend = self.service.get_revenue_trend(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            interval='day'
        )

        self.assertEqual(trend['interval'], 'day')
        self.assertIn('data', trend)
        self.assertGreater(len(trend['data']), 0)

        # Verify data points
        for point in trend['data']:
            self.assertIn('revenue', point)
            self.assertIn('transaction_date', point)

    def test_get_category_breakdown(self):
        """Test category breakdown."""
        breakdown = self.service.get_category_breakdown(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            transaction_type='sale'
        )

        self.assertIn('categories', breakdown)
        self.assertIn('total_amount', breakdown)
        self.assertGreater(breakdown['total_amount'], 0)

        # Verify category data
        for category in breakdown['categories']:
            self.assertIn('category', category)
            self.assertIn('amount', category)
            self.assertIn('percentage', category)
            self.assertIn('count', category)

    def test_get_platform_performance(self):
        """Test platform performance metrics."""
        performance = self.service.get_platform_performance(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        self.assertIn('platforms', performance)
        self.assertGreater(len(performance['platforms']), 0)

        # Verify platform data
        for platform in performance['platforms']:
            self.assertIn('platform', platform)
            self.assertIn('revenue', platform)
            self.assertIn('transactions', platform)
            self.assertIn('avg_transaction_value', platform)

    def test_get_customer_analytics(self):
        """Test customer analytics."""
        analytics = self.service.get_customer_analytics(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            limit=5
        )

        self.assertIn('top_customers', analytics)
        customers = analytics['top_customers']

        # Should have limited to 5 customers
        self.assertLessEqual(len(customers), 5)

        # Verify customer data
        for customer in customers:
            self.assertIn('customer_name', customer)
            self.assertIn('total_revenue', customer)
            self.assertIn('orders', customer)
            self.assertIn('avg_order_value', customer)

    def test_get_cash_flow_analysis(self):
        """Test cash flow analysis."""
        cash_flow = self.service.get_cash_flow_analysis(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            interval='month'
        )

        self.assertEqual(cash_flow['interval'], 'month')
        self.assertIn('data', cash_flow)

        # Verify cash flow data
        for period in cash_flow['data']:
            self.assertIn('inflow', period)
            self.assertIn('outflow', period)
            self.assertIn('net_flow', period)

            # Net flow should be inflow - outflow
            expected_net = period['inflow'] - period['outflow']
            self.assertAlmostEqual(period['net_flow'], expected_net, places=2)

    def test_get_growth_metrics(self):
        """Test growth metrics calculation."""
        growth = self.service.get_growth_metrics(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        self.assertIn('revenue_growth_rate', growth)
        self.assertIn('customer_growth_rate', growth)
        self.assertIn('metrics', growth)

        # Verify metrics structure
        metrics = growth['metrics']
        self.assertIn('current_revenue', metrics)
        self.assertIn('previous_revenue', metrics)
        self.assertIn('current_customers', metrics)
        self.assertIn('previous_customers', metrics)

    def test_period_over_period_comparison(self):
        """Test period-over-period comparison in KPIs."""
        # Create older transactions for comparison
        old_date = date(2023, 12, 1)
        for i in range(10):
            Transaction.objects.create(
                organization=self.organization,
                transaction_type='sale',
                transaction_date=old_date + timedelta(days=i),
                gross_amount=Decimal('50.00'),
                net_amount=Decimal('50.00')
            )

        kpis = self.service.get_dashboard_kpis(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        # Should have comparison data
        self.assertIn('previous', kpis['revenue'])
        self.assertGreater(kpis['revenue']['previous'], 0)

    def test_category_breakdown_filtering(self):
        """Test category breakdown with different transaction types."""
        # Sales breakdown
        sales_breakdown = self.service.get_category_breakdown(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            transaction_type='sale'
        )

        # Expense breakdown
        expense_breakdown = self.service.get_category_breakdown(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            transaction_type='expense'
        )

        # Should have different amounts
        self.assertNotEqual(
            sales_breakdown['total_amount'],
            expense_breakdown['total_amount']
        )

    def test_revenue_trend_different_intervals(self):
        """Test revenue trend with different intervals."""
        # Daily
        daily_trend = self.service.get_revenue_trend(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            interval='day'
        )

        # Monthly
        monthly_trend = self.service.get_revenue_trend(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            interval='month'
        )

        # Daily should have more data points
        self.assertGreater(len(daily_trend['data']), len(monthly_trend['data']))
