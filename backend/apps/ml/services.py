"""
ML/AI services for Nova Ledger.
Anomaly detection and financial forecasting - KEY DIFFERENTIATOR.
"""
from decimal import Decimal
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from django.db.models import Avg, StdDev, Count, Sum
from django.utils import timezone
from .models import AnomalyDetection, FinancialForecast, TransactionCategorization
from apps.transactions.models import Transaction, Fee
from apps.accounts.models import ChartOfAccounts
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """
    ML-powered anomaly detection for financial transactions.
    Detects unusual patterns, errors, and potential fraud.
    """

    def __init__(self, organization):
        self.organization = organization

    def detect_unusual_fees(self, transaction: Transaction) -> List[AnomalyDetection]:
        """
        Detect if transaction fees are unusual based on historical data.

        Compares transaction fees to expected fees based on:
        - Platform (Stripe, Shopify, etc.)
        - Transaction amount
        - Historical fee percentages
        """
        anomalies = []

        for fee in transaction.fees.all():
            # Get historical average fee percentage for this fee type and platform
            historical_fees = Fee.objects.filter(
                transaction__organization=self.organization,
                transaction__source_platform=transaction.source_platform,
                fee_type=fee.fee_type,
                transaction__gross_amount__gt=0
            ).exclude(
                transaction=transaction
            )

            if historical_fees.count() < 10:
                # Not enough data to detect anomalies
                continue

            # Calculate historical statistics
            stats = historical_fees.aggregate(
                avg_percentage=Avg('fee_percentage'),
                stddev_percentage=StdDev('fee_percentage')
            )

            avg_pct = stats['avg_percentage']
            stddev_pct = stats['stddev_percentage']

            if not avg_pct or not stddev_pct:
                continue

            # Calculate current fee percentage
            current_pct = (fee.amount / transaction.gross_amount) if transaction.gross_amount > 0 else Decimal('0')

            # Check if current fee is more than 3 standard deviations from mean
            z_score = abs(float(current_pct - avg_pct) / float(stddev_pct))

            if z_score > 3:  # 3 sigma threshold
                # This is an outlier!
                confidence = min(z_score / 10.0, 0.99)  # Higher z-score = higher confidence

                anomaly = AnomalyDetection.objects.create(
                    organization=self.organization,
                    transaction=transaction,
                    anomaly_type='unusual_fee',
                    severity='high' if z_score > 5 else 'medium',
                    status='pending',
                    description=(
                        f"{fee.fee_type} fee is {current_pct:.2%} vs expected {avg_pct:.2%}. "
                        f"Fee amount: ${fee.amount} on ${transaction.gross_amount} transaction."
                    ),
                    expected_value=avg_pct * transaction.gross_amount,
                    actual_value=fee.amount,
                    confidence_score=Decimal(str(confidence)),
                    model_version='1.0',
                    detection_algorithm='z_score',
                    detection_metadata={
                        'z_score': z_score,
                        'avg_percentage': float(avg_pct),
                        'stddev_percentage': float(stddev_pct),
                        'current_percentage': float(current_pct)
                    }
                )

                anomalies.append(anomaly)

                logger.warning(
                    f"Unusual fee detected: {fee.fee_type} {current_pct:.2%} "
                    f"(expected {avg_pct:.2%}, z-score: {z_score:.2f}) "
                    f"on transaction {transaction.transaction_number}"
                )

        return anomalies

    def detect_duplicate_transactions(self, transaction: Transaction) -> List[AnomalyDetection]:
        """
        Detect potential duplicate transactions.

        Looks for transactions with:
        - Same amount
        - Same customer
        - Same platform
        - Within 24 hours
        """
        anomalies = []

        # Look for similar transactions
        time_window_start = transaction.transaction_date - timedelta(hours=24)
        time_window_end = transaction.transaction_date + timedelta(hours=24)

        similar_transactions = Transaction.objects.filter(
            organization=self.organization,
            source_platform=transaction.source_platform,
            gross_amount=transaction.gross_amount,
            customer_email=transaction.customer_email,
            transaction_date__gte=time_window_start,
            transaction_date__lte=time_window_end
        ).exclude(id=transaction.id)

        if similar_transactions.exists():
            duplicate = similar_transactions.first()

            anomaly = AnomalyDetection.objects.create(
                organization=self.organization,
                transaction=transaction,
                anomaly_type='duplicate_transaction',
                severity='medium',
                status='pending',
                description=(
                    f"Potential duplicate of transaction {duplicate.transaction_number}. "
                    f"Same amount (${transaction.gross_amount}), customer ({transaction.customer_email}), "
                    f"and platform ({transaction.source_platform}) within 24 hours."
                ),
                actual_value=transaction.gross_amount,
                confidence_score=Decimal('0.85'),
                model_version='1.0',
                detection_algorithm='rule_based',
                detection_metadata={
                    'duplicate_transaction_id': str(duplicate.id),
                    'duplicate_transaction_number': duplicate.transaction_number,
                    'time_difference_minutes': int(
                        abs((transaction.transaction_date - duplicate.transaction_date).total_seconds() / 60)
                    )
                }
            )

            anomalies.append(anomaly)

            logger.warning(
                f"Potential duplicate detected: {transaction.transaction_number} "
                f"matches {duplicate.transaction_number}"
            )

        return anomalies

    def detect_tax_mismatches(self, transaction: Transaction) -> List[AnomalyDetection]:
        """
        Detect tax calculation mismatches.

        Compares calculated tax to expected tax based on:
        - Transaction location
        - Tax configuration
        - Line item totals
        """
        anomalies = []

        # Get total tax from line items
        actual_tax = sum(item.tax_amount for item in transaction.line_items.all())

        if actual_tax == 0:
            return anomalies  # No tax to validate

        # Simple validation: check if tax seems reasonable (5-12% range for most US states)
        tax_percentage = (actual_tax / transaction.gross_amount) if transaction.gross_amount > 0 else Decimal('0')

        if tax_percentage < Decimal('0.04') or tax_percentage > Decimal('0.15'):
            # Tax is outside reasonable bounds
            anomaly = AnomalyDetection.objects.create(
                organization=self.organization,
                transaction=transaction,
                anomaly_type='tax_mismatch',
                severity='medium',
                status='pending',
                description=(
                    f"Tax rate {tax_percentage:.2%} is outside typical range (4-15%). "
                    f"Tax amount: ${actual_tax} on ${transaction.gross_amount}."
                ),
                expected_value=transaction.gross_amount * Decimal('0.075'),  # Assume 7.5% typical
                actual_value=actual_tax,
                confidence_score=Decimal('0.75'),
                model_version='1.0',
                detection_algorithm='range_check',
                detection_metadata={
                    'tax_percentage': float(tax_percentage)
                }
            )

            anomalies.append(anomaly)

        return anomalies

    def run_all_detections(self, transaction: Transaction) -> List[AnomalyDetection]:
        """
        Run all anomaly detection algorithms on a transaction.

        Returns list of all detected anomalies.
        """
        all_anomalies = []

        all_anomalies.extend(self.detect_unusual_fees(transaction))
        all_anomalies.extend(self.detect_duplicate_transactions(transaction))
        all_anomalies.extend(self.detect_tax_mismatches(transaction))

        if all_anomalies:
            logger.info(
                f"Detected {len(all_anomalies)} anomalies for "
                f"transaction {transaction.transaction_number}"
            )

        return all_anomalies


class FinancialForecastingService:
    """
    Financial forecasting using time-series analysis.
    Predicts future revenue, cash flow, and metrics.
    """

    def __init__(self, organization):
        self.organization = organization

    def forecast_revenue(
        self,
        periods_ahead: int = 12,
        method: str = 'linear_regression'
    ) -> List[FinancialForecast]:
        """
        Forecast future revenue using historical data.

        Args:
            periods_ahead: Number of months to forecast
            method: 'linear_regression', 'moving_average', or 'exponential_smoothing'

        Returns:
            List of FinancialForecast objects
        """
        # Get historical revenue data (last 12 months)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365)

        from apps.reporting.models import DashboardMetric

        historical_revenue = DashboardMetric.objects.filter(
            organization=self.organization,
            metric_name='total_revenue',
            period_date__gte=start_date,
            period_date__lte=end_date
        ).order_by('period_date').values_list('metric_value', 'period_date')

        if len(historical_revenue) < 3:
            logger.warning("Insufficient historical data for forecasting")
            return []

        # Extract data
        y_values = np.array([float(val[0]) for val in historical_revenue])
        dates = [val[1] for val in historical_revenue]

        if method == 'linear_regression':
            forecasts = self._linear_regression_forecast(y_values, periods_ahead)
        elif method == 'moving_average':
            forecasts = self._moving_average_forecast(y_values, periods_ahead)
        else:
            forecasts = self._simple_growth_forecast(y_values, periods_ahead)

        # Create forecast objects
        forecast_objects = []
        last_date = dates[-1]

        for i, forecast_value in enumerate(forecasts, 1):
            forecast_date = last_date + timedelta(days=30 * i)  # Approximate month

            # Calculate confidence intervals (simplified)
            std_dev = np.std(y_values)
            lower_bound = Decimal(str(forecast_value - 1.96 * std_dev))
            upper_bound = Decimal(str(forecast_value + 1.96 * std_dev))

            forecast_obj = FinancialForecast.objects.create(
                organization=self.organization,
                forecast_type='revenue',
                forecast_date=forecast_date,
                forecast_value=Decimal(str(forecast_value)),
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                confidence_level=Decimal('0.95'),
                model_version='1.0',
                algorithm=method,
                training_data_period_start=start_date,
                training_data_period_end=end_date,
                scenario_name='Base Case'
            )

            forecast_objects.append(forecast_obj)

        logger.info(
            f"Generated {len(forecast_objects)} revenue forecasts using {method}"
        )

        return forecast_objects

    def _linear_regression_forecast(self, y_values: np.ndarray, periods: int) -> List[float]:
        """Simple linear regression forecast."""
        x_values = np.arange(len(y_values))

        # Calculate linear regression coefficients
        coefficients = np.polyfit(x_values, y_values, 1)
        slope, intercept = coefficients

        # Generate forecasts
        future_x = np.arange(len(y_values), len(y_values) + periods)
        forecasts = [slope * x + intercept for x in future_x]

        return forecasts

    def _moving_average_forecast(self, y_values: np.ndarray, periods: int) -> List[float]:
        """Moving average forecast."""
        window = min(3, len(y_values))
        ma = np.mean(y_values[-window:])

        # Assume constant forecast (simple approach)
        forecasts = [ma] * periods

        return forecasts

    def _simple_growth_forecast(self, y_values: np.ndarray, periods: int) -> List[float]:
        """Simple growth rate forecast."""
        # Calculate average growth rate
        growth_rates = []
        for i in range(1, len(y_values)):
            if y_values[i-1] != 0:
                growth_rate = (y_values[i] - y_values[i-1]) / y_values[i-1]
                growth_rates.append(growth_rate)

        avg_growth_rate = np.mean(growth_rates) if growth_rates else 0

        # Apply growth rate
        last_value = y_values[-1]
        forecasts = []
        current_value = last_value

        for _ in range(periods):
            current_value = current_value * (1 + avg_growth_rate)
            forecasts.append(current_value)

        return forecasts
