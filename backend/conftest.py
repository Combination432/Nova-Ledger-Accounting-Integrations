"""
Shared pytest fixtures for Nova Ledger tests.
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import Organization, ChartOfAccounts, SalesChannel
from apps.inventory.models import InventoryItem, InventoryLocation


@pytest.fixture
def organization(db):
    """Create a test organization."""
    return Organization.objects.create(
        name="Test Organization",
        fiscal_year_end=timezone.now().date(),
        default_currency="USD"
    )


@pytest.fixture
def chart_of_accounts(db, organization):
    """Create a basic chart of accounts."""
    accounts = {
        'inventory': ChartOfAccounts.objects.create(
            organization=organization,
            account_number="1200",
            account_name="Inventory Asset",
            account_type="asset",
            account_subtype="inventory"
        ),
        'cogs': ChartOfAccounts.objects.create(
            organization=organization,
            account_number="5000",
            account_name="Cost of Goods Sold",
            account_type="cogs",
            account_subtype="product_costs"
        ),
        'revenue': ChartOfAccounts.objects.create(
            organization=organization,
            account_number="4000",
            account_name="Sales Revenue",
            account_type="revenue",
            account_subtype="product_sales"
        ),
        'cash': ChartOfAccounts.objects.create(
            organization=organization,
            account_number="1000",
            account_name="Cash",
            account_type="asset",
            account_subtype="cash"
        ),
    }
    return accounts


@pytest.fixture
def sales_channel(db, organization):
    """Create a test sales channel."""
    return SalesChannel.objects.create(
        organization=organization,
        name="Test Shopify Store",
        channel_type="shopify",
        is_active=True
    )


@pytest.fixture
def inventory_location(db, organization):
    """Create a test inventory location."""
    return InventoryLocation.objects.create(
        organization=organization,
        name="Main Warehouse",
        location_type="warehouse",
        is_default=True
    )


@pytest.fixture
def inventory_item(db, organization, chart_of_accounts):
    """Create a test inventory item."""
    return InventoryItem.objects.create(
        organization=organization,
        sku="TEST-001",
        name="Test Product",
        costing_method="average",
        current_average_cost=Decimal('10.00'),
        total_quantity_on_hand=Decimal('100'),
        inventory_asset_account=chart_of_accounts['inventory'],
        cogs_account=chart_of_accounts['cogs']
    )
