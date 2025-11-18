"""
ML models for Nova Ledger.
AI-powered error detection, anomaly detection, and financial forecasting.
"""
from django.db import models
from apps.accounts.models import Organization
import uuid


class AnomalyDetection(models.Model):
    """
    ML-detected anomalies in transactions.
    """
    ANOMALY_TYPES = [
        ('unusual_fee', 'Unusual Fee Amount'),
        ('duplicate_transaction', 'Potential Duplicate'),
        ('missing_data', 'Missing Required Data'),
        ('outlier_amount', 'Outlier Amount'),
        ('fee_mismatch', 'Fee Percentage Mismatch'),
        ('tax_mismatch', 'Tax Calculation Mismatch'),
        ('reconciliation_gap', 'Reconciliation Gap'),
        ('fraud_indicator', 'Potential Fraud'),
    ]

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
        ('ignored', 'Ignored'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='anomalies')

    # Anomaly details
    anomaly_type = models.CharField(max_length=50, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')

    # Related transaction
    transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.CASCADE,
        related_name='anomalies',
        null=True,
        blank=True
    )

    # Detection details
    description = models.TextField()
    expected_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    actual_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4)  # 0.0 to 1.0

    # ML model info
    model_version = models.CharField(max_length=50)
    detection_algorithm = models.CharField(max_length=100)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # Metadata
    detection_metadata = models.JSONField(default=dict)

    detected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'anomaly_detections'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['organization', 'status', 'severity']),
        ]


class FinancialForecast(models.Model):
    """
    AI-generated financial forecasts.
    """
    FORECAST_TYPES = [
        ('revenue', 'Revenue Forecast'),
        ('cash_flow', 'Cash Flow Forecast'),
        ('deferred_revenue', 'Deferred Revenue Forecast'),
        ('mrr', 'MRR Forecast'),
        ('churn', 'Churn Rate Forecast'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='forecasts')

    # Forecast details
    forecast_type = models.CharField(max_length=50, choices=FORECAST_TYPES)
    forecast_date = models.DateField()  # The date being forecasted
    forecast_value = models.DecimalField(max_digits=15, decimal_places=2)

    # Confidence intervals
    lower_bound = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    upper_bound = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    confidence_level = models.DecimalField(max_digits=5, decimal_places=4, default=0.95)

    # Model details
    model_version = models.CharField(max_length=50)
    algorithm = models.CharField(max_length=100)
    training_data_period_start = models.DateField()
    training_data_period_end = models.DateField()

    # Scenario
    scenario_name = models.CharField(max_length=255, blank=True)  # e.g., "Conservative", "Optimistic"
    scenario_assumptions = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'financial_forecasts'
        ordering = ['forecast_date']


class TransactionCategorization(models.Model):
    """
    AI-powered transaction categorization and account suggestions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='categorizations')

    # Pattern matching
    description_pattern = models.CharField(max_length=255)
    vendor_pattern = models.CharField(max_length=255, blank=True)
    amount_range_min = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    amount_range_max = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Suggested categorization
    suggested_account = models.ForeignKey('accounts.ChartOfAccounts', on_delete=models.CASCADE)
    category_name = models.CharField(max_length=255)

    # ML confidence
    confidence_score = models.DecimalField(max_digits=5, decimal_places=4)
    times_applied = models.IntegerField(default=0)
    times_correct = models.IntegerField(default=0)

    # Auto-apply
    auto_apply = models.BooleanField(default=False)
    auto_apply_threshold = models.DecimalField(max_digits=5, decimal_places=4, default=0.95)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transaction_categorizations'


class MLModelMetrics(models.Model):
    """
    Track performance metrics for ML models.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ml_metrics')

    # Model identification
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50)
    model_type = models.CharField(max_length=50)  # e.g., 'anomaly_detection', 'forecasting'

    # Performance metrics
    accuracy = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    precision = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    recall = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)

    # Forecasting-specific metrics
    mae = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # Mean Absolute Error
    rmse = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # Root Mean Squared Error

    # Training details
    training_samples = models.IntegerField()
    test_samples = models.IntegerField()
    training_date = models.DateTimeField()

    # Additional metrics
    metrics_data = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ml_model_metrics'
        ordering = ['-created_at']
