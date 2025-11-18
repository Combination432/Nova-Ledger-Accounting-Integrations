"""
Revenue Recognition models for Nova Ledger.
ASC 606 compliant deferred revenue tracking for SaaS businesses.
"""
from django.db import models
from apps.accounts.models import Organization, ChartOfAccounts
from decimal import Decimal
import uuid


class RevenueContract(models.Model):
    """
    Customer contracts for revenue recognition (ASC 606).
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='revenue_contracts')

    # Contract details
    contract_number = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=255)
    customer_id = models.CharField(max_length=255, blank=True)

    # Dates
    contract_date = models.DateField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Contract value
    total_contract_value = models.DecimalField(max_digits=15, decimal_places=2)
    recognized_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    deferred_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # GL accounts
    deferred_revenue_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='deferred_revenue_contracts'
    )
    revenue_account = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.PROTECT,
        related_name='revenue_contracts'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'revenue_contracts'
        ordering = ['-contract_date']

    def __str__(self):
        return f"Contract {self.contract_number} - {self.customer_name}"


class RevenueSchedule(models.Model):
    """
    Revenue recognition schedule for deferred revenue.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(RevenueContract, on_delete=models.CASCADE, related_name='schedules')

    # Schedule details
    period_start_date = models.DateField()
    period_end_date = models.DateField()
    recognition_date = models.DateField()

    # Amounts
    scheduled_amount = models.DecimalField(max_digits=15, decimal_places=2)
    recognized_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Recognition status
    is_recognized = models.BooleanField(default=False)
    recognized_at = models.DateTimeField(null=True, blank=True)
    journal_entry = models.ForeignKey(
        'transactions.JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'revenue_schedules'
        ordering = ['recognition_date']


class SubscriptionMetric(models.Model):
    """
    SaaS metrics tracking (MRR, ARR, Churn, LTV, CAC).
    """
    METRIC_TYPES = [
        ('mrr', 'Monthly Recurring Revenue'),
        ('arr', 'Annual Recurring Revenue'),
        ('new_mrr', 'New MRR'),
        ('expansion_mrr', 'Expansion MRR'),
        ('contraction_mrr', 'Contraction MRR'),
        ('churned_mrr', 'Churned MRR'),
        ('customer_count', 'Customer Count'),
        ('ltv', 'Customer Lifetime Value'),
        ('cac', 'Customer Acquisition Cost'),
        ('churn_rate', 'Churn Rate'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='subscription_metrics')

    # Metric details
    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES)
    metric_date = models.DateField(db_index=True)

    # Value
    value = models.DecimalField(max_digits=15, decimal_places=2)

    # Dimensions
    product_category = models.CharField(max_length=100, blank=True)
    customer_segment = models.CharField(max_length=100, blank=True)
    acquisition_channel = models.CharField(max_length=100, blank=True)

    # Metadata
    calculation_details = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subscription_metrics'
        ordering = ['-metric_date']
        indexes = [
            models.Index(fields=['organization', 'metric_type', 'metric_date']),
        ]


class CustomerCohort(models.Model):
    """
    Customer cohort analysis for retention and LTV tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='customer_cohorts')

    # Cohort definition
    cohort_name = models.CharField(max_length=255)
    cohort_date = models.DateField()  # e.g., "January 2024" cohort

    # Cohort characteristics
    acquisition_channel = models.CharField(max_length=100, blank=True)
    product_category = models.CharField(max_length=100, blank=True)

    # Cohort metrics
    initial_customers = models.IntegerField(default=0)
    current_customers = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_ltv = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    retention_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table =='customer_cohorts'
        ordering = ['-cohort_date']
