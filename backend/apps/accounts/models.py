"""
Account models for Nova Ledger.
Handles user accounts, organizations, and chart of accounts.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
import uuid


class User(AbstractUser):
    """Extended user model with organization support."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE, related_name='users', null=True)
    role = models.CharField(max_length=50, choices=[
        ('owner', 'Owner'),
        ('admin', 'Administrator'),
        ('accountant', 'Accountant'),
        ('viewer', 'Viewer'),
    ], default='viewer')
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'


class Organization(models.Model):
    """Organization/Company model."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    tax_id = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    fiscal_year_end = models.DateField()
    accounting_method = models.CharField(max_length=20, choices=[
        ('accrual', 'Accrual'),
        ('cash', 'Cash'),
    ], default='accrual')

    # Subscription & Billing
    subscription_tier = models.CharField(max_length=20, choices=[
        ('growth', 'Growth'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ], default='growth')
    monthly_transaction_limit = models.IntegerField(default=5000)

    # Settings
    enable_inventory_tracking = models.BooleanField(default=False)
    enable_multi_currency = models.BooleanField(default=False)
    enable_landed_costs = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'organizations'

    def __str__(self):
        return self.name


class ChartOfAccounts(models.Model):
    """Chart of Accounts - GL Account definitions."""

    ACCOUNT_TYPES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
        ('cogs', 'Cost of Goods Sold'),
    ]

    ACCOUNT_SUBTYPES = [
        # Assets
        ('cash', 'Cash and Cash Equivalents'),
        ('accounts_receivable', 'Accounts Receivable'),
        ('inventory', 'Inventory'),
        ('prepaid_expenses', 'Prepaid Expenses'),
        ('fixed_assets', 'Fixed Assets'),

        # Liabilities
        ('accounts_payable', 'Accounts Payable'),
        ('credit_card', 'Credit Card'),
        ('sales_tax_payable', 'Sales Tax Payable'),
        ('deferred_revenue', 'Deferred Revenue'),
        ('loans_payable', 'Loans Payable'),

        # Equity
        ('owners_equity', 'Owner\'s Equity'),
        ('retained_earnings', 'Retained Earnings'),

        # Revenue
        ('sales_revenue', 'Sales Revenue'),
        ('service_revenue', 'Service Revenue'),
        ('other_income', 'Other Income'),

        # Expenses
        ('operating_expense', 'Operating Expense'),
        ('payment_processing_fees', 'Payment Processing Fees'),
        ('shipping_expense', 'Shipping Expense'),
        ('platform_fees', 'Platform Fees'),

        # COGS
        ('product_costs', 'Product Costs'),
        ('freight_in', 'Freight In'),
        ('customs_duties', 'Customs and Duties'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='accounts')

    # Account identification
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    account_subtype = models.CharField(max_length=50, choices=ACCOUNT_SUBTYPES)

    # Account details
    description = models.TextField(blank=True)
    parent_account = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_accounts')

    # Integration mapping
    quickbooks_id = models.CharField(max_length=255, blank=True)
    xero_id = models.CharField(max_length=255, blank=True)
    netsuite_id = models.CharField(max_length=255, blank=True)

    # Account settings
    is_active = models.BooleanField(default=True)
    is_sub_account = models.BooleanField(default=False)

    # Balance tracking
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chart_of_accounts'
        unique_together = ['organization', 'account_number']
        ordering = ['account_number']

    def __str__(self):
        return f"{self.account_number} - {self.account_name}"


class SalesChannel(models.Model):
    """Sales channels (Shopify, Amazon, etc.) for multi-channel tracking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='sales_channels')

    name = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=50, choices=[
        ('shopify', 'Shopify'),
        ('amazon', 'Amazon'),
        ('ebay', 'eBay'),
        ('woocommerce', 'WooCommerce'),
        ('bigcommerce', 'BigCommerce'),
        ('square', 'Square POS'),
        ('stripe', 'Stripe Direct'),
        ('other', 'Other'),
    ])

    # Channel-specific GL accounts
    revenue_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT, related_name='revenue_channels')
    fee_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT, related_name='fee_channels')
    tax_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT, related_name='tax_channels')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales_channels'

    def __str__(self):
        return f"{self.name} ({self.channel_type})"
