"""
Transaction models for Nova Ledger.
Handles all financial transactions, journal entries, and reconciliation.
"""
from django.db import models
from apps.accounts.models import Organization, ChartOfAccounts, SalesChannel
import uuid
from decimal import Decimal


class Transaction(models.Model):
    """
    Core transaction model representing any financial transaction.
    This is the heart of Nova Ledger's transaction processing.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='transactions')

    # Transaction identification
    transaction_number = models.CharField(max_length=100, unique=True)
    external_id = models.CharField(max_length=255, db_index=True)  # ID from source platform
    transaction_type = models.CharField(max_length=50, choices=[
        ('sale', 'Sale'),
        ('refund', 'Refund'),
        ('payment', 'Payment'),
        ('fee', 'Fee'),
        ('payout', 'Payout'),
        ('adjustment', 'Adjustment'),
        ('inventory', 'Inventory'),
        ('tax', 'Tax'),
    ])

    # Source information
    source_platform = models.CharField(max_length=50, choices=[
        ('shopify', 'Shopify'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('square', 'Square'),
        ('amazon', 'Amazon'),
        ('manual', 'Manual Entry'),
    ])
    sales_channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True)

    # Transaction details
    transaction_date = models.DateTimeField(db_index=True)
    description = models.TextField()
    reference_number = models.CharField(max_length=100, blank=True)

    # Amounts
    gross_amount = models.DecimalField(max_digits=15, decimal_places=2)
    net_amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')

    # Customer information
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_id = models.CharField(max_length=255, blank=True)

    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciliation_date = models.DateTimeField(null=True, blank=True)
    bank_transaction = models.ForeignKey('BankTransaction', on_delete=models.SET_NULL, null=True, blank=True)

    # Journal Entry link
    journal_entry = models.ForeignKey('JournalEntry', on_delete=models.SET_NULL, null=True, blank=True)

    # Metadata
    raw_data = models.JSONField(default=dict)  # Store original API response
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transactions'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['organization', 'transaction_date']),
            models.Index(fields=['external_id', 'source_platform']),
        ]

    def __str__(self):
        return f"{self.transaction_number} - {self.transaction_type} - {self.gross_amount}"


class TransactionLineItem(models.Model):
    """
    Line items within a transaction (e.g., individual products in a sale).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='line_items')

    # Product information
    product_id = models.CharField(max_length=255, blank=True)
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    variant_id = models.CharField(max_length=255, blank=True)

    # Quantity and pricing
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    total_price = models.DecimalField(max_digits=15, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Tax
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)

    # COGS (populated after inventory lookup)
    unit_cost = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_cogs = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    # Inventory link
    inventory_item = models.ForeignKey('inventory.InventoryItem', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transaction_line_items'


class Fee(models.Model):
    """
    Detailed fee breakdown for each transaction.
    This is key to Nova Ledger's "hyper-detail" advantage.
    """
    FEE_TYPES = [
        ('payment_processing', 'Payment Processing Fee'),
        ('platform_fee', 'Platform Fee (e.g., Amazon FBA)'),
        ('subscription_fee', 'Subscription Fee'),
        ('transaction_fee', 'Transaction Fee'),
        ('currency_conversion', 'Currency Conversion Fee'),
        ('chargeback_fee', 'Chargeback Fee'),
        ('dispute_fee', 'Dispute Fee'),
        ('refund_fee', 'Refund Fee'),
        ('shipping_fee', 'Shipping Fee'),
        ('other', 'Other Fee'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='fees')

    fee_type = models.CharField(max_length=50, choices=FEE_TYPES)
    fee_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # GL account mapping
    expense_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)

    # Details
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fees'


class JournalEntry(models.Model):
    """
    General Ledger Journal Entry.
    Each transaction creates a balanced journal entry.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='journal_entries')

    # Entry identification
    entry_number = models.CharField(max_length=100, unique=True)
    entry_date = models.DateField(db_index=True)
    posting_date = models.DateField()

    # Entry details
    description = models.TextField()
    reference = models.CharField(max_length=255, blank=True)

    # Entry status
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('void', 'Void'),
    ], default='draft')

    # Sync status
    synced_to_accounting = models.BooleanField(default=False)
    sync_date = models.DateTimeField(null=True, blank=True)
    quickbooks_id = models.CharField(max_length=255, blank=True)
    xero_id = models.CharField(max_length=255, blank=True)

    # Metadata
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'journal_entries'
        ordering = ['-entry_date']

    def __str__(self):
        return f"JE-{self.entry_number}"

    def is_balanced(self):
        """Check if journal entry debits equal credits."""
        total_debits = sum(line.debit_amount for line in self.lines.all())
        total_credits = sum(line.credit_amount for line in self.lines.all())
        return abs(total_debits - total_credits) < Decimal('0.01')


class JournalEntryLine(models.Model):
    """Individual line items within a journal entry."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')

    account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)
    description = models.TextField(blank=True)

    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    # Dimensional tracking
    sales_channel = models.ForeignKey(SalesChannel, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    class_tracking = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'journal_entry_lines'


class BankTransaction(models.Model):
    """
    Bank transactions/payouts for reconciliation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='bank_transactions')

    # Bank details
    bank_account = models.ForeignKey('BankAccount', on_delete=models.CASCADE)
    transaction_date = models.DateField(db_index=True)
    description = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    # Reconciliation
    is_reconciled = models.BooleanField(default=False)
    reconciled_date = models.DateTimeField(null=True, blank=True)

    # Source
    source_platform = models.CharField(max_length=50, blank=True)
    external_id = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bank_transactions'
        ordering = ['-transaction_date']


class BankAccount(models.Model):
    """Bank account configuration."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='bank_accounts')

    account_name = models.CharField(max_length=255)
    account_number_last4 = models.CharField(max_length=4)
    bank_name = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default='USD')

    # GL account mapping
    gl_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bank_accounts'

    def __str__(self):
        return f"{self.account_name} (...{self.account_number_last4})"


class ReconciliationRule(models.Model):
    """
    AI-powered reconciliation rules for automatic matching.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='reconciliation_rules')

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Matching criteria
    source_platform = models.CharField(max_length=50, blank=True)
    amount_tolerance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    days_tolerance = models.IntegerField(default=3)

    # Conditions (stored as JSON)
    conditions = models.JSONField(default=dict)

    # Auto-apply
    auto_apply = models.BooleanField(default=False)
    priority = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reconciliation_rules'
        ordering = ['-priority']
