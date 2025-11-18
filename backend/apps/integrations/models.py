"""
Integration models for Nova Ledger.
Manages connections to accounting systems, e-commerce platforms, and payment processors.
"""
from django.db import models
from apps.accounts.models import Organization
from django.utils import timezone
import uuid


class Integration(models.Model):
    """
    Master integration configuration.
    """
    INTEGRATION_TYPES = [
        # Accounting/ERP
        ('quickbooks_online', 'QuickBooks Online'),
        ('quickbooks_desktop', 'QuickBooks Desktop'),
        ('xero', 'Xero'),
        ('netsuite', 'NetSuite'),
        ('sage_intacct', 'Sage Intacct'),

        # E-commerce
        ('shopify', 'Shopify'),
        ('amazon_seller', 'Amazon Seller Central'),
        ('woocommerce', 'WooCommerce'),
        ('bigcommerce', 'BigCommerce'),
        ('ebay', 'eBay'),

        # Payment Processors
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('square', 'Square'),
        ('authorize_net', 'Authorize.net'),

        # Other
        ('custom_api', 'Custom API'),
    ]

    SYNC_DIRECTIONS = [
        ('import', 'Import Only'),
        ('export', 'Export Only'),
        ('bidirectional', 'Bidirectional'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='integrations')

    # Integration details
    integration_type = models.CharField(max_length=50, choices=INTEGRATION_TYPES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Configuration
    sync_direction = models.CharField(max_length=20, choices=SYNC_DIRECTIONS, default='import')
    is_active = models.BooleanField(default=True)

    # Authentication (encrypted)
    auth_credentials = models.JSONField(default=dict)  # Encrypted OAuth tokens, API keys, etc.
    oauth_access_token = models.TextField(blank=True)
    oauth_refresh_token = models.TextField(blank=True)
    oauth_token_expiry = models.DateTimeField(null=True, blank=True)

    # Connection status
    is_connected = models.BooleanField(default=False)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    connection_error = models.TextField(blank=True)

    # Sync settings
    auto_sync_enabled = models.BooleanField(default=True)
    sync_frequency_minutes = models.IntegerField(default=15)  # How often to sync
    last_sync_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True)

    # Platform-specific settings
    settings = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integrations'
        unique_together = ['organization', 'integration_type']

    def __str__(self):
        return f"{self.name} ({self.integration_type})"


class SyncLog(models.Model):
    """
    Logs of sync operations for debugging and monitoring.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partially Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='sync_logs')

    # Sync details
    sync_type = models.CharField(max_length=50)  # e.g., 'transactions', 'inventory', 'customers'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Results
    records_processed = models.IntegerField(default=0)
    records_created = models.IntegerField(default=0)
    records_updated = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)

    # Error handling
    error_message = models.TextField(blank=True)
    error_details = models.JSONField(null=True, blank=True)

    # Metadata
    sync_metadata = models.JSONField(default=dict)

    class Meta:
        db_table = 'sync_logs'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.integration.name} - {self.sync_type} - {self.status}"


class WebhookEndpoint(models.Model):
    """
    Webhook endpoints for real-time data sync.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='webhooks')

    # Endpoint details
    webhook_url = models.URLField()
    secret_key = models.CharField(max_length=255)  # For signature verification

    # Event types this webhook handles
    event_types = models.JSONField(default=list)  # e.g., ['order.created', 'order.updated']

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'webhook_endpoints'


class WebhookEvent(models.Model):
    """
    Incoming webhook events (for debugging and replay).
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook_endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='events')

    # Event details
    event_type = models.CharField(max_length=100)
    event_id = models.CharField(max_length=255, db_index=True)  # External event ID

    # Payload
    payload = models.JSONField()
    headers = models.JSONField(default=dict)

    # Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'webhook_events'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['event_id', 'event_type']),
        ]


class FieldMapping(models.Model):
    """
    Field mappings between Nova Ledger and external platforms.
    Allows customization of how data is mapped.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='field_mappings')

    # Source and destination
    nova_ledger_field = models.CharField(max_length=255)
    external_field = models.CharField(max_length=255)

    # Transformation rules
    transformation_type = models.CharField(max_length=50, choices=[
        ('direct', 'Direct Mapping'),
        ('concatenate', 'Concatenate Fields'),
        ('split', 'Split Field'),
        ('formula', 'Formula/Expression'),
        ('lookup', 'Lookup Table'),
    ], default='direct')

    transformation_config = models.JSONField(default=dict)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'field_mappings'


class AccountMapping(models.Model):
    """
    GL Account mappings between Nova Ledger and external accounting systems.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(Integration, on_delete=models.CASCADE, related_name='account_mappings')

    # Nova Ledger account
    nova_ledger_account = models.ForeignKey('accounts.ChartOfAccounts', on_delete=models.CASCADE)

    # External system account
    external_account_id = models.CharField(max_length=255)
    external_account_name = models.CharField(max_length=255)

    # Sync settings
    sync_enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'account_mappings'
        unique_together = ['integration', 'nova_ledger_account']


class TaxConfiguration(models.Model):
    """
    Tax configuration for multi-jurisdictional tax calculation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='tax_configurations')

    # Tax jurisdiction
    country = models.CharField(max_length=2)  # ISO country code
    state_province = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Tax details
    tax_name = models.CharField(max_length=255)  # e.g., "California Sales Tax"
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4)  # e.g., 0.0725 for 7.25%

    # Product applicability
    applies_to_products = models.BooleanField(default=True)
    applies_to_shipping = models.BooleanField(default=False)

    # Nexus tracking
    has_nexus = models.BooleanField(default=True)
    nexus_date = models.DateField(null=True, blank=True)

    # GL account
    tax_liability_account = models.ForeignKey('accounts.ChartOfAccounts', on_delete=models.PROTECT)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tax_configurations'

    def __str__(self):
        return f"{self.tax_name} - {self.tax_rate * 100}%"
