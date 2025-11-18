"""
Webhook processing service for all platforms.
Handles signature verification, event processing, and retry logic.
"""
from typing import Dict, Optional
import hmac
import hashlib
import json
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

from ..models import WebhookEvent, WebhookEndpoint, Integration

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Service for processing webhooks from all platforms.
    Handles signature verification and event processing.
    """

    def __init__(self, platform: str):
        """
        Initialize webhook service for a platform.

        Args:
            platform: Platform name (shopify, stripe, quickbooks)
        """
        self.platform = platform.lower()

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        headers: Dict = None
    ) -> bool:
        """
        Verify webhook signature for the platform.

        Args:
            payload: Raw webhook payload (bytes)
            signature: Signature from webhook header
            secret: Webhook secret key
            headers: Optional headers dict for additional verification

        Returns:
            True if signature is valid
        """
        if self.platform == 'shopify':
            return self._verify_shopify_signature(payload, signature, secret)
        elif self.platform == 'stripe':
            return self._verify_stripe_signature(payload, signature, secret, headers)
        elif self.platform == 'quickbooks':
            return self._verify_quickbooks_signature(payload, signature, secret, headers)
        else:
            logger.warning(f"No signature verification implemented for {self.platform}")
            return True  # Allow for development

    def _verify_shopify_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """
        Verify Shopify webhook signature.

        Shopify uses HMAC-SHA256 with base64 encoding.
        Header: X-Shopify-Hmac-SHA256
        """
        import base64

        computed_hmac = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        )
        computed_signature = base64.b64encode(computed_hmac.digest()).decode()

        return hmac.compare_digest(computed_signature, signature)

    def _verify_stripe_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        headers: Dict
    ) -> bool:
        """
        Verify Stripe webhook signature.

        Stripe uses HMAC-SHA256 with timestamp to prevent replay attacks.
        Header: Stripe-Signature (format: "t=timestamp,v1=signature")
        """
        # Parse signature header
        sig_parts = {}
        for part in signature.split(','):
            key, value = part.split('=', 1)
            sig_parts[key] = value

        timestamp = sig_parts.get('t')
        signature_value = sig_parts.get('v1')

        if not timestamp or not signature_value:
            logger.warning("Invalid Stripe signature format")
            return False

        # Check timestamp (prevent replay attacks older than 5 minutes)
        try:
            timestamp_int = int(timestamp)
            current_timestamp = int(timezone.now().timestamp())

            if current_timestamp - timestamp_int > 300:  # 5 minutes
                logger.warning("Stripe webhook timestamp too old")
                return False
        except ValueError:
            logger.warning("Invalid Stripe timestamp")
            return False

        # Compute signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        computed_hmac = hmac.new(
            secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        )
        computed_signature = computed_hmac.hexdigest()

        return hmac.compare_digest(computed_signature, signature_value)

    def _verify_quickbooks_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
        headers: Dict
    ) -> bool:
        """
        Verify QuickBooks webhook signature.

        QuickBooks uses HMAC-SHA256 with specific payload format.
        Header: intuit-signature
        """
        # QuickBooks webhook verification
        # Signature is computed from: request body + webhook token

        computed_hmac = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        )
        computed_signature = computed_hmac.hexdigest()

        return hmac.compare_digest(computed_signature, signature)

    def process_webhook(
        self,
        integration: Integration,
        event_type: str,
        payload: Dict,
        event_id: Optional[str] = None
    ) -> WebhookEvent:
        """
        Process a webhook event.

        Args:
            integration: Integration that received the webhook
            event_type: Type of event (e.g., 'orders/create')
            payload: Webhook payload
            event_id: Optional unique event ID from platform

        Returns:
            Created WebhookEvent
        """
        # Check for duplicate event
        if event_id:
            existing = WebhookEvent.objects.filter(
                event_id=event_id,
                webhook_endpoint__integration=integration
            ).first()

            if existing:
                logger.info(f"Duplicate webhook event {event_id}, skipping")
                existing.retry_count += 1
                existing.save(update_fields=['retry_count'])
                return existing

        # Get or create webhook endpoint
        webhook_endpoint, _ = WebhookEndpoint.objects.get_or_create(
            integration=integration,
            webhook_url=self._get_webhook_url(integration),
            defaults={
                'secret_key': integration.settings.get('webhook_secret', ''),
                'event_types': [event_type]
            }
        )

        # Create webhook event
        webhook_event = WebhookEvent.objects.create(
            webhook_endpoint=webhook_endpoint,
            event_type=event_type,
            event_id=event_id or '',
            payload=payload,
            status='pending',
            received_at=timezone.now()
        )

        # Process event asynchronously
        try:
            self._process_event(integration, event_type, payload, webhook_event)
            webhook_event.status = 'processed'
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=['status', 'processed_at'])

        except Exception as e:
            logger.error(f"Failed to process webhook event {webhook_event.id}: {str(e)}")
            webhook_event.status = 'failed'
            webhook_event.error_message = str(e)
            webhook_event.save(update_fields=['status', 'error_message'])

            # Schedule retry
            if webhook_event.retry_count < 3:
                self._schedule_retry(webhook_event)

        return webhook_event

    def _process_event(
        self,
        integration: Integration,
        event_type: str,
        payload: Dict,
        webhook_event: WebhookEvent
    ):
        """
        Process webhook event based on platform and event type.

        Args:
            integration: Integration
            event_type: Event type
            payload: Event payload
            webhook_event: WebhookEvent record
        """
        if self.platform == 'shopify':
            self._process_shopify_event(integration, event_type, payload)
        elif self.platform == 'stripe':
            self._process_stripe_event(integration, event_type, payload)
        elif self.platform == 'quickbooks':
            self._process_quickbooks_event(integration, event_type, payload)
        else:
            logger.warning(f"No event processor for platform {self.platform}")

    def _process_shopify_event(
        self,
        integration: Integration,
        event_type: str,
        payload: Dict
    ):
        """
        Process Shopify webhook event.

        Event types:
        - orders/create, orders/updated, orders/cancelled
        - products/create, products/update, products/delete
        - customers/create, customers/update, customers/delete
        - fulfillments/create, fulfillments/update
        """
        from .shopify_service import ShopifyIntegrationService
        from ..sync_engine import SyncEngine

        # Map event types to sync actions
        if event_type in ['orders/create', 'orders/updated', 'orders/cancelled']:
            # Process order
            service = ShopifyIntegrationService(integration)
            sync_engine = SyncEngine(integration)

            # Parse order from payload
            order_data = service._parse_order(payload)

            if order_data:
                # Check if transaction exists
                from apps.transactions.models import Transaction
                existing = Transaction.objects.filter(
                    organization=integration.organization,
                    source_platform='shopify',
                    source_id=order_data['transaction']['source_id']
                ).first()

                if existing:
                    # Update existing transaction
                    sync_engine._update_transaction(existing, order_data)
                    logger.info(f"Updated Shopify order {order_data['transaction']['source_id']}")
                else:
                    # Create new transaction
                    sync_engine._create_transaction(order_data)
                    logger.info(f"Created Shopify order {order_data['transaction']['source_id']}")

        elif event_type in ['products/create', 'products/update', 'products/delete']:
            logger.info(f"Shopify product event received: {event_type}")
            # Product events don't directly affect accounting
            # Could be used for inventory tracking in future

        elif event_type in ['customers/create', 'customers/update', 'customers/delete']:
            logger.info(f"Shopify customer event received: {event_type}")
            # Could update customer records in future

        else:
            logger.info(f"Unhandled Shopify event type: {event_type}")

    def _process_stripe_event(
        self,
        integration: Integration,
        event_type: str,
        payload: Dict
    ):
        """
        Process Stripe webhook event.

        Event types:
        - charge.succeeded, charge.failed, charge.refunded
        - payment_intent.succeeded, payment_intent.payment_failed
        - invoice.payment_succeeded, invoice.payment_failed
        - payout.paid, payout.failed
        - transfer.created, transfer.updated
        """
        from .stripe_service import StripeIntegrationService
        from ..sync_engine import SyncEngine

        service = StripeIntegrationService(integration)
        sync_engine = SyncEngine(integration)

        # Get event data
        data = payload.get('data', {}).get('object', {})

        if event_type.startswith('charge.'):
            # Process charge
            charge_data = service._parse_charge(data)
            if charge_data:
                from apps.transactions.models import Transaction
                existing = Transaction.objects.filter(
                    organization=integration.organization,
                    source_platform='stripe',
                    source_id=charge_data['transaction']['source_id']
                ).first()

                if existing:
                    sync_engine._update_transaction(existing, charge_data)
                else:
                    sync_engine._create_transaction(charge_data)

        elif event_type.startswith('payout.'):
            # Process payout
            if event_type == 'payout.paid':
                payout_data = service._parse_payout(data)
                if payout_data:
                    # Trigger payout reconstruction
                    from .payout_reconstructor import PayoutReconstructionService
                    reconstructor = PayoutReconstructionService(integration)
                    reconstructor.reconstruct_payout(data['id'])

        elif event_type.startswith('invoice.'):
            # Process invoice
            invoice_data = service._parse_invoice(data)
            if invoice_data:
                from apps.transactions.models import Transaction
                existing = Transaction.objects.filter(
                    organization=integration.organization,
                    source_platform='stripe',
                    source_id=invoice_data['transaction']['source_id']
                ).first()

                if existing:
                    sync_engine._update_transaction(existing, invoice_data)
                else:
                    sync_engine._create_transaction(invoice_data)

        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")

    def _process_quickbooks_event(
        self,
        integration: Integration,
        event_type: str,
        payload: Dict
    ):
        """
        Process QuickBooks webhook event.

        Event types:
        - Invoice, Customer, Payment, Item, etc.

        QuickBooks webhooks are entity-based, not event-based.
        """
        from .quickbooks_service import QuickBooksIntegrationService

        # QuickBooks webhook format:
        # {
        #   "eventNotifications": [
        #     {
        #       "realmId": "123456",
        #       "dataChangeEvent": {
        #         "entities": [
        #           {
        #             "name": "Invoice",
        #             "id": "123",
        #             "operation": "Create|Update|Delete"
        #           }
        #         ]
        #       }
        #     }
        #   ]
        # }

        service = QuickBooksIntegrationService(integration)

        for notification in payload.get('eventNotifications', []):
            data_change = notification.get('dataChangeEvent', {})
            realm_id = notification.get('realmId')

            # Verify realm ID matches
            if realm_id != integration.auth_credentials.get('realm_id'):
                logger.warning(f"Realm ID mismatch: {realm_id}")
                continue

            for entity in data_change.get('entities', []):
                entity_name = entity.get('name')
                entity_id = entity.get('id')
                operation = entity.get('operation')

                logger.info(
                    f"QuickBooks {operation} event for {entity_name} {entity_id}"
                )

                # Fetch and process entity
                if entity_name == 'Invoice' and operation in ['Create', 'Update']:
                    # Trigger invoice sync
                    service.sync_invoices(incremental=True)

                elif entity_name == 'Payment' and operation in ['Create', 'Update']:
                    # Trigger payment sync
                    service.sync_payments(incremental=True)

                elif entity_name == 'Customer' and operation in ['Create', 'Update']:
                    # Could update customer records
                    pass

    def _schedule_retry(self, webhook_event: WebhookEvent):
        """
        Schedule webhook event retry.

        Args:
            webhook_event: Failed webhook event
        """
        from celery import current_app

        # Exponential backoff: 1min, 5min, 30min
        retry_delays = [60, 300, 1800]
        delay = retry_delays[min(webhook_event.retry_count, len(retry_delays) - 1)]

        # Queue retry task (would use Celery in production)
        logger.info(
            f"Scheduling retry for webhook {webhook_event.id} "
            f"in {delay} seconds (attempt {webhook_event.retry_count + 1})"
        )

        # In production, use:
        # current_app.send_task(
        #     'integrations.tasks.retry_webhook',
        #     args=[str(webhook_event.id)],
        #     countdown=delay
        # )

    def _get_webhook_url(self, integration: Integration) -> str:
        """
        Get webhook URL for integration.

        Args:
            integration: Integration

        Returns:
            Webhook URL
        """
        # This would be the public webhook endpoint
        base_url = getattr(settings, 'WEBHOOK_BASE_URL', 'https://api.example.com')
        return f"{base_url}/api/integrations/webhooks/{self.platform}/"

    def register_webhooks(self, integration: Integration) -> Dict:
        """
        Register webhooks with the platform.

        Args:
            integration: Integration to register webhooks for

        Returns:
            Dict with registration results
        """
        if self.platform == 'shopify':
            return self._register_shopify_webhooks(integration)
        elif self.platform == 'stripe':
            return self._register_stripe_webhooks(integration)
        elif self.platform == 'quickbooks':
            return self._register_quickbooks_webhooks(integration)
        else:
            raise ValueError(f"Webhook registration not supported for {self.platform}")

    def _register_shopify_webhooks(self, integration: Integration) -> Dict:
        """
        Register Shopify webhooks via API.
        """
        import shopify

        from .oauth_service import OAuthService

        oauth_service = OAuthService('shopify', integration.organization)
        access_token = oauth_service.get_valid_token(integration)

        shop = integration.auth_credentials.get('shop')
        session = shopify.Session(f"{shop}.myshopify.com", '2024-01', access_token)
        shopify.ShopifyResource.activate_session(session)

        webhook_url = self._get_webhook_url(integration)

        topics = [
            'orders/create',
            'orders/updated',
            'orders/cancelled',
            'orders/paid',
        ]

        created_webhooks = []

        for topic in topics:
            try:
                webhook = shopify.Webhook()
                webhook.topic = topic
                webhook.address = webhook_url
                webhook.format = 'json'

                if webhook.save():
                    created_webhooks.append({
                        'topic': topic,
                        'id': webhook.id,
                        'address': webhook.address
                    })
                    logger.info(f"Registered Shopify webhook: {topic}")

            except Exception as e:
                logger.error(f"Failed to register Shopify webhook {topic}: {str(e)}")

        return {
            'platform': 'shopify',
            'webhooks_created': len(created_webhooks),
            'webhooks': created_webhooks
        }

    def _register_stripe_webhooks(self, integration: Integration) -> Dict:
        """
        Register Stripe webhooks via API.
        """
        import stripe

        from .oauth_service import OAuthService

        oauth_service = OAuthService('stripe', integration.organization)
        access_token = oauth_service.get_valid_token(integration)

        stripe.api_key = access_token

        webhook_url = self._get_webhook_url(integration)

        enabled_events = [
            'charge.succeeded',
            'charge.refunded',
            'payment_intent.succeeded',
            'invoice.payment_succeeded',
            'payout.paid',
        ]

        try:
            webhook_endpoint = stripe.WebhookEndpoint.create(
                url=webhook_url,
                enabled_events=enabled_events,
            )

            logger.info(f"Registered Stripe webhook: {webhook_endpoint.id}")

            return {
                'platform': 'stripe',
                'webhook_id': webhook_endpoint.id,
                'url': webhook_url,
                'enabled_events': enabled_events
            }

        except Exception as e:
            logger.error(f"Failed to register Stripe webhook: {str(e)}")
            raise

    def _register_quickbooks_webhooks(self, integration: Integration) -> Dict:
        """
        Register QuickBooks webhooks.

        Note: QuickBooks webhooks are configured through the developer portal,
        not via API.
        """
        logger.info(
            "QuickBooks webhooks must be configured in the Intuit Developer Portal. "
            "Navigate to your app settings and add the webhook URL."
        )

        webhook_url = self._get_webhook_url(integration)

        return {
            'platform': 'quickbooks',
            'message': 'Configure webhook in Intuit Developer Portal',
            'webhook_url': webhook_url,
            'entity_types': ['Invoice', 'Payment', 'Customer']
        }
