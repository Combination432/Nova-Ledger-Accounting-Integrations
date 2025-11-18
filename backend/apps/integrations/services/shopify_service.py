"""
Shopify integration service for Nova Ledger.
Handles order sync, inventory sync, and payout reconstruction.
"""
import shopify
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from apps.transactions.models import Transaction, TransactionLineItem, Fee
from apps.integrations.models import Integration, SyncLog
from apps.inventory.models import InventoryItem
import logging

logger = logging.getLogger(__name__)


class ShopifyIntegrationService:
    """
    Service for syncing data from Shopify to Nova Ledger.
    """

    def __init__(self, integration: Integration):
        self.integration = integration
        self.organization = integration.organization

        # Initialize Shopify API session
        shop_url = integration.settings.get('shop_url')
        access_token = integration.oauth_access_token

        if not shop_url or not access_token:
            raise ValueError("Shopify shop URL and access token are required")

        self.session = shopify.Session(shop_url, '2024-01', access_token)
        shopify.ShopifyResource.activate_session(self.session)

    def sync_orders(self, start_date=None, end_date=None):
        """
        Sync orders from Shopify.
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='shopify_orders',
            status='running'
        )

        try:
            # Default to last 30 days if no date range provided
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()

            # Fetch orders from Shopify
            orders = shopify.Order.find(
                status='any',
                created_at_min=start_date.isoformat(),
                created_at_max=end_date.isoformat(),
                limit=250
            )

            processed_count = 0
            created_count = 0
            updated_count = 0
            failed_count = 0

            for order in orders:
                try:
                    transaction = self._process_order(order)
                    processed_count += 1

                    if transaction:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    logger.error(f"Failed to process Shopify order {order.id}: {str(e)}")
                    failed_count += 1

            # Update sync log
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = processed_count
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.duration_seconds = (
                sync_log.completed_at - sync_log.started_at
            ).total_seconds()
            sync_log.save()

            logger.info(
                f"Shopify order sync completed: {processed_count} orders processed, "
                f"{created_count} created, {updated_count} updated, {failed_count} failed"
            )

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.completed_at = timezone.now()
            sync_log.save()
            logger.error(f"Shopify order sync failed: {str(e)}")
            raise

    def _process_order(self, shopify_order):
        """
        Process a single Shopify order into Nova Ledger transaction.
        """
        # Check if transaction already exists
        external_id = f"shopify_order_{shopify_order.id}"
        transaction, created = Transaction.objects.get_or_create(
            organization=self.organization,
            external_id=external_id,
            source_platform='shopify',
            defaults={
                'transaction_number': f"SH-{shopify_order.order_number}",
                'transaction_type': 'sale',
                'transaction_date': shopify_order.created_at,
                'description': f"Shopify Order #{shopify_order.order_number}",
                'gross_amount': Decimal(str(shopify_order.total_price)),
                'net_amount': Decimal(str(shopify_order.total_price)),
                'currency': shopify_order.currency,
                'customer_name': f"{shopify_order.customer.first_name} {shopify_order.customer.last_name}" if shopify_order.customer else "",
                'customer_email': shopify_order.customer.email if shopify_order.customer else "",
                'customer_id': str(shopify_order.customer.id) if shopify_order.customer else "",
                'raw_data': shopify_order.to_dict(),
            }
        )

        if not created:
            # Update existing transaction
            transaction.raw_data = shopify_order.to_dict()
            transaction.save()

        # Process line items
        self._process_line_items(transaction, shopify_order.line_items)

        # Process fees (Shopify doesn't have direct fees, but we track shipping)
        if shopify_order.total_shipping_price_set:
            self._create_shipping_fee(transaction, shopify_order)

        return transaction if created else None

    def _process_line_items(self, transaction, line_items):
        """
        Process Shopify line items.
        """
        # Clear existing line items
        transaction.line_items.all().delete()

        for item in line_items:
            # Try to find matching inventory item
            inventory_item = None
            if item.sku:
                try:
                    inventory_item = InventoryItem.objects.get(
                        organization=self.organization,
                        sku=item.sku
                    )
                except InventoryItem.DoesNotExist:
                    pass

            TransactionLineItem.objects.create(
                transaction=transaction,
                product_id=str(item.product_id) if item.product_id else "",
                product_name=item.name,
                sku=item.sku or "",
                variant_id=str(item.variant_id) if item.variant_id else "",
                quantity=Decimal(str(item.quantity)),
                unit_price=Decimal(str(item.price)),
                total_price=Decimal(str(item.price)) * Decimal(str(item.quantity)),
                discount_amount=Decimal(str(item.total_discount or 0)),
                tax_amount=Decimal(str(sum(tax.price for tax in item.tax_lines))),
                inventory_item=inventory_item,
                unit_cost=inventory_item.current_average_cost if inventory_item else None,
                total_cogs=inventory_item.current_average_cost * Decimal(str(item.quantity)) if inventory_item else None,
            )

    def _create_shipping_fee(self, transaction, shopify_order):
        """
        Create shipping fee entry.
        """
        shipping_amount = Decimal(str(shopify_order.total_shipping_price_set['shop_money']['amount']))

        if shipping_amount > 0:
            # Find or create shipping expense account
            from apps.accounts.models import ChartOfAccounts
            shipping_account, _ = ChartOfAccounts.objects.get_or_create(
                organization=self.organization,
                account_type='expense',
                account_subtype='shipping_expense',
                defaults={
                    'account_number': '5100',
                    'account_name': 'Shipping Expense',
                }
            )

            Fee.objects.create(
                transaction=transaction,
                fee_type='shipping_fee',
                fee_name='Shopify Shipping',
                amount=shipping_amount,
                expense_account=shipping_account
            )

    def sync_inventory(self):
        """
        Sync inventory levels from Shopify.
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='shopify_inventory',
            status='running'
        )

        try:
            products = shopify.Product.find(limit=250)

            processed_count = 0
            created_count = 0
            updated_count = 0

            for product in products:
                for variant in product.variants:
                    inventory_item, created = InventoryItem.objects.update_or_create(
                        organization=self.organization,
                        sku=variant.sku or f"shopify_{variant.id}",
                        defaults={
                            'name': f"{product.title} - {variant.title}",
                            'description': product.body_html or "",
                            'shopify_product_id': str(product.id),
                            'shopify_variant_id': str(variant.id),
                            'product_type': product.product_type or "",
                            'total_quantity_on_hand': Decimal(str(variant.inventory_quantity or 0)),
                        }
                    )

                    processed_count += 1
                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = processed_count
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.save()

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

    def __del__(self):
        """Clean up Shopify session."""
        try:
            shopify.ShopifyResource.clear_session()
        except:
            pass
