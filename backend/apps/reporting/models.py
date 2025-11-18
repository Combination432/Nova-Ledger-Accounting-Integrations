"""
Reporting models for Nova Ledger.
Financial intelligence, profitability analysis, and dashboard metrics.
"""
from django.db import models
from apps.accounts.models import Organization, SalesChannel
import uuid


class ChannelProfitability(models.Model):
    """
    Channel-level profitability analysis.
    This is a KEY DIFFERENTIATOR - automatic P&L by sales channel.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='channel_profitability')
    sales_channel = models.ForeignKey(SalesChannel, on_delete=models.CASCADE, related_name='profitability_data')

    # Period
    period_start = models.DateField(db_index=True)
    period_end = models.DateField()
    period_type = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], default='monthly')

    # Revenue metrics
    gross_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    returns_refunds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_sales = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Costs
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_processing_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    platform_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    shipping_costs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Calculated metrics
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # Additional metrics
    order_count = models.IntegerField(default=0)
    average_order_value = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    units_sold = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'channel_profitability'
        unique_together = ['sales_channel', 'period_start', 'period_type']
        ordering = ['-period_start']


class ProductProfitability(models.Model):
    """
    SKU-level profitability tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='product_profitability')
    inventory_item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)

    # Period
    period_start = models.DateField(db_index=True)
    period_end = models.DateField()
    period_type = models.CharField(max_length=20, default='monthly')

    # Sales metrics
    units_sold = models.DecimalField(max_digits=15, decimal_places=3, default=0)
    gross_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    net_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Costs
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_cogs_per_unit = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    allocated_fees = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Profitability
    gross_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    gross_margin_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # By channel (optional dimension)
    sales_channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product_profitability'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_profitability'
        ordering = ['-period_start']


class DashboardMetric(models.Model):
    """
    Pre-calculated dashboard metrics for fast loading.
    """
    METRIC_CATEGORIES = [
        ('revenue', 'Revenue'),
        ('profitability', 'Profitability'),
        ('inventory', 'Inventory'),
        ('cash_flow', 'Cash Flow'),
        ('saas', 'SaaS Metrics'),
        ('operational', 'Operational'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='dashboard_metrics')

    # Metric identification
    metric_name = models.CharField(max_length=100)
    metric_category = models.CharField(max_length=50, choices=METRIC_CATEGORIES)
    metric_label = models.CharField(max_length=255)

    # Value
    metric_value = models.DecimalField(max_digits=15, decimal_places=2)
    metric_unit = models.CharField(max_length=20, blank=True)  # e.g., 'USD', '%', 'count'

    # Period
    period_date = models.DateField(db_index=True)
    period_type = models.CharField(max_length=20, default='monthly')

    # Comparison
    previous_period_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    change_percent = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    # Metadata
    calculation_notes = models.TextField(blank=True)
    dimensions = models.JSONField(default=dict)  # Store additional dimensions

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dashboard_metrics'
        unique_together = ['organization', 'metric_name', 'period_date']
        ordering = ['-period_date']


class FinancialReport(models.Model):
    """
    Generated financial reports (P&L, Balance Sheet, Cash Flow).
    """
    REPORT_TYPES = [
        ('profit_loss', 'Profit & Loss'),
        ('balance_sheet', 'Balance Sheet'),
        ('cash_flow', 'Cash Flow Statement'),
        ('trial_balance', 'Trial Balance'),
        ('channel_pl', 'Channel P&L'),
        ('product_profitability', 'Product Profitability'),
    ]

    FORMAT_TYPES = [
        ('json', 'JSON'),
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='financial_reports')

    # Report details
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    report_name = models.CharField(max_length=255)

    # Period
    period_start = models.DateField()
    period_end = models.DateField()

    # Filters/dimensions
    sales_channel = models.ForeignKey(
        SalesChannel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    filters = models.JSONField(default=dict)

    # Report data
    report_data = models.JSONField()
    format_type = models.CharField(max_length=20, choices=FORMAT_TYPES, default='json')
    file_path = models.CharField(max_length=500, blank=True)  # If saved as file

    # Generation details
    generated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'financial_reports'
        ordering = ['-generated_at']


class ReconciliationReport(models.Model):
    """
    Bank reconciliation reports.
    """
    STATUS_CHOICES = [
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('needs_review', 'Needs Review'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='reconciliation_reports')

    # Reconciliation period
    period_start = models.DateField()
    period_end = models.DateField()

    # Bank account
    bank_account = models.ForeignKey('transactions.BankAccount', on_delete=models.CASCADE)

    # Summary
    beginning_balance = models.DecimalField(max_digits=15, decimal_places=2)
    ending_balance = models.DecimalField(max_digits=15, decimal_places=2)
    reconciled_transactions = models.IntegerField(default=0)
    unreconciled_transactions = models.IntegerField(default=0)
    total_deposits = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_withdrawals = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    reconciled_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    reconciled_at = models.DateTimeField(null=True, blank=True)

    # Notes
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reconciliation_reports'
        ordering = ['-period_end']
