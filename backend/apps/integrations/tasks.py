"""
Celery tasks for integration processing.
"""
from celery import shared_task
from .models import WebhookEvent, Integration
from .services import ShopifyIntegrationService, StripeIntegrationService
import logging

logger = logging.getLogger(__name__)


@shared_task
def process_shopify_webhook(webhook_event_id):
    """Process Shopify webhook event asynchronously."""
    try:
        event = WebhookEvent.objects.get(id=webhook_event_id)
        event.status = 'processing'
        event.save()
        
        integration = event.webhook_endpoint.integration
        service = ShopifyIntegrationService(integration)
        
        # Handle different event types
        if event.event_type == 'orders/create':
            # Process new order
            order_data = event.payload
            # service.process_order(order_data)
            pass
        
        event.status = 'processed'
        event.save()
        
    except Exception as e:
        logger.error(f"Failed to process Shopify webhook {webhook_event_id}: {str(e)}")
        event = WebhookEvent.objects.get(id=webhook_event_id)
        event.status = 'failed'
        event.error_message = str(e)
        event.save()


@shared_task
def process_stripe_webhook(webhook_event_id):
    """Process Stripe webhook event asynchronously."""
    try:
        event = WebhookEvent.objects.get(id=webhook_event_id)
        event.status = 'processing'
        event.save()
        
        integration = event.webhook_endpoint.integration
        service = StripeIntegrationService(integration)
        
        # Handle different event types
        if event.event_type == 'charge.succeeded':
            charge_id = event.payload.get('data', {}).get('object', {}).get('id')
            # Process charge
            pass
        
        event.status = 'processed'
        event.save()
        
    except Exception as e:
        logger.error(f"Failed to process Stripe webhook {webhook_event_id}: {str(e)}")
        event = WebhookEvent.objects.get(id=webhook_event_id)
        event.status = 'failed'
        event.error_message = str(e)
        event.save()
