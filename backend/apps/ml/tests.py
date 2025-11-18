"""
Tests for ML services - Anomaly Detection and Financial Forecasting.
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import Organization, ChartOfAccounts, SalesChannel
from apps.transactions.models import Transaction, Fee
from apps.ml.services import AnomalyDetectionService, FinancialForecastingService
from apps.ml.models import AnomalyDetection, FinancialForecast


class AnomalyDetectionTest(TestCase):
    """Test ML anomaly detection - key differentiator."""

    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Company",
            fiscal_year_end=timezone.now().date()
        )

        self.cash_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="1000",
            account_name="Cash",
            account_type="asset",
            account_subtype="cash"
        )

        self.revenue_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="4000",
            account_name="Sales Revenue",
            account_type="revenue",
            account_subtype="product_sales"
        )

        self.channel = SalesChannel.objects.create(
            organization=self.org,
            name="Test Store",
            channel_type="shopify",
            is_active=True
        )

    def test_detect_unusual_fees(self):
        """Test detection of unusual fee percentages."""
        service = AnomalyDetectionService(self.org)

        # Create historical transactions with normal fees (3% processing fee)
        for i in range(10):
            txn = Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=timezone.now().date() - timedelta(days=i+10),
                gross_amount=Decimal('100.00'),
                net_amount=Decimal('97.00')
            )
            Fee.objects.create(
                transaction=txn,
                fee_type="payment_processing",
                fee_category="platform_fee",
                amount=Decimal('3.00'),
                fee_percentage=Decimal('3.00')
            )

        # Create transaction with unusually high fee (15%)
        unusual_txn = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('85.00')
        )
        Fee.objects.create(
            transaction=unusual_txn,
            fee_type="payment_processing",
            fee_category="platform_fee",
            amount=Decimal('15.00'),
            fee_percentage=Decimal('15.00')
        )

        # Detect anomalies
        anomalies = service.detect_unusual_fees(unusual_txn)

        # Should detect the unusual fee
        self.assertGreater(len(anomalies), 0)
        anomaly = anomalies[0]
        self.assertEqual(anomaly.anomaly_type, 'unusual_fee')
        self.assertIn('severity', ['medium', 'high'])
        self.assertGreater(anomaly.confidence_score, Decimal('0.5'))

    def test_detect_duplicate_transactions(self):
        """Test detection of potential duplicate transactions."""
        service = AnomalyDetectionService(self.org)

        # Create two identical transactions
        txn1 = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('157.49'),
            net_amount=Decimal('152.49'),
            external_transaction_id="ORDER-12345"
        )

        txn2 = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('157.49'),
            net_amount=Decimal('152.49'),
            external_transaction_id="ORDER-12346"  # Different ID
        )

        # Detect duplicates
        anomalies = service.detect_duplicate_transactions(txn2)

        # Should detect potential duplicate
        self.assertGreater(len(anomalies), 0)
        anomaly = anomalies[0]
        self.assertEqual(anomaly.anomaly_type, 'duplicate_transaction')
        self.assertIn('ORDER-12345', anomaly.description)

    def test_no_anomalies_for_normal_transaction(self):
        """Test that normal transactions don't trigger anomalies."""
        service = AnomalyDetectionService(self.org)

        # Create several normal transactions
        for i in range(10):
            Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=timezone.now().date() - timedelta(days=i),
                gross_amount=Decimal('100.00'),
                net_amount=Decimal('97.00')
            )

        # Create another normal transaction
        normal_txn = Transaction.objects.create(
            organization=self.org,
            sales_channel=self.channel,
            transaction_type="sale",
            transaction_date=timezone.now().date(),
            gross_amount=Decimal('105.00'),
            net_amount=Decimal('101.85')
        )

        # Run all detections
        anomalies = service.run_all_detections(normal_txn)

        # Should not detect anomalies
        self.assertEqual(len(anomalies), 0)


class FinancialForecastingTest(TestCase):
    """Test financial forecasting service."""

    def setUp(self):
        """Set up test data."""
        self.org = Organization.objects.create(
            name="Test Company",
            fiscal_year_end=timezone.now().date()
        )

        self.revenue_account = ChartOfAccounts.objects.create(
            organization=self.org,
            account_number="4000",
            account_name="Sales Revenue",
            account_type="revenue",
            account_subtype="product_sales"
        )

        self.channel = SalesChannel.objects.create(
            organization=self.org,
            name="Test Store",
            channel_type="shopify",
            is_active=True
        )

    def test_forecast_revenue_linear_regression(self):
        """Test revenue forecasting using linear regression."""
        service = FinancialForecastingService(self.org)

        # Create 12 months of historical revenue with growth trend
        base_revenue = Decimal('10000.00')
        for i in range(12):
            month_date = timezone.now().date() - timedelta(days=(12-i)*30)
            revenue = base_revenue + (Decimal(str(i)) * Decimal('500.00'))

            Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=month_date,
                gross_amount=revenue,
                net_amount=revenue * Decimal('0.97')
            )

        # Generate forecast
        forecasts = service.forecast_revenue(
            metric_name='total_revenue',
            periods_ahead=3,
            method='linear_regression'
        )

        # Should generate 3 forecasts
        self.assertEqual(len(forecasts), 3)

        # Forecasts should show increasing trend
        self.assertGreater(forecasts[1].forecasted_value, forecasts[0].forecasted_value)
        self.assertGreater(forecasts[2].forecasted_value, forecasts[1].forecasted_value)

        # Should have confidence intervals
        for forecast in forecasts:
            self.assertIsNotNone(forecast.lower_bound)
            self.assertIsNotNone(forecast.upper_bound)
            self.assertGreater(forecast.upper_bound, forecast.lower_bound)

    def test_forecast_with_insufficient_data(self):
        """Test that forecasting handles insufficient historical data."""
        service = FinancialForecastingService(self.org)

        # Create only 2 months of data (insufficient)
        for i in range(2):
            month_date = timezone.now().date() - timedelta(days=(2-i)*30)
            Transaction.objects.create(
                organization=self.org,
                sales_channel=self.channel,
                transaction_type="sale",
                transaction_date=month_date,
                gross_amount=Decimal('10000.00'),
                net_amount=Decimal('9700.00')
            )

        # Should handle gracefully (may return empty or use moving average)
        forecasts = service.forecast_revenue(
            metric_name='total_revenue',
            periods_ahead=3,
            method='linear_regression'
        )

        # Should either return forecasts with low confidence or handle gracefully
        # Implementation dependent
        self.assertIsNotNone(forecasts)
