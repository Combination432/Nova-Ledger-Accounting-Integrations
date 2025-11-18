"""
Webhook handlers for Nova Ledger.
Secure webhook processing with signature verification.
"""
import hmac
import hashlib
import json
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import WebhookEndpoint, WebhookEvent
from .services import ShopifyIntegrationService, StripeIntegrationService
import logging

logger = logging.getLogger(__name__)


def verify_shopify_webhook(request, secret):
    """Verify Shopify webhook signature."""
    hmac_header = request.headers.get('X-Shopify-Hmac-SHA256')
    
    if not hmac_header:
        return False
    
    computed_hmac = hmac.new(
        secret.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).digest()
    
    import base64
    computed_hmac_b64 = base64.b64encode(computed_hmac).decode()
    
    return hmac.compare_digest(computed_hmac_b64, hmac_header)


def verify_stripe_webhook(request, secret):
    """Verify Stripe webhook signature."""
    import stripe
    
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        return False
    
    try:
        stripe.Webhook.construct_event(
            request.body,
            sig_header,
            secret
        )
        return True
    except Exception as e:
        logger.error(f"Stripe webhook verification failed: {str(e)}")
        return False


@csrf_exempt
@require_POST
def shopify_webhook(request):
    """Handle Shopify webhooks."""
    # Get webhook endpoint configuration
    try:
        webhook_endpoint = WebhookEndpoint.objects.get(
            integration__integration_type='shopify',
            integration__organization__is_active=True,
            is_active=True
        )
    except WebhookEndpoint.DoesNotExist:
        logger.error("No active Shopify webhook endpoint configured")
        return HttpResponseBadRequest("Webhook not configured")
    
    # Verify signature
    if not verify_shopify_webhook(request, webhook_endpoint.secret_key):
        logger.warning("Shopify webhook signature verification failed")
        return HttpResponseBadRequest("Invalid signature")
    
    # Parse event
    event_type = request.headers.get('X-Shopify-Topic')
    shop_domain = request.headers.get('X-Shopify-Shop-Domain')
    
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    
    # Store webhook event
    webhook_event = WebhookEvent.objects.create(
        webhook_endpoint=webhook_endpoint,
        event_type=event_type,
        event_id=payload.get('id', ''),
        payload=payload,
        headers=dict(request.headers),
        status='pending'
    )
    
    # Process event asynchronously
    from .tasks import process_shopify_webhook
    process_shopify_webhook.delay(webhook_event.id)
    
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks."""
    try:
        webhook_endpoint = WebhookEndpoint.objects.get(
            integration__integration_type='stripe',
            integration__organization__is_active=True,
            is_active=True
        )
    except WebhookEndpoint.DoesNotExist:
        logger.error("No active Stripe webhook endpoint configured")
        return HttpResponseBadRequest("Webhook not configured")
    
    # Verify signature
    if not verify_stripe_webhook(request, webhook_endpoint.secret_key):
        logger.warning("Stripe webhook signature verification failed")
        return HttpResponseBadRequest("Invalid signature")
    
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")
    
    event_type = payload.get('type')
    event_id = payload.get('id')
    
    # Store webhook event
    webhook_event = WebhookEvent.objects.create(
        webhook_endpoint=webhook_endpoint,
        event_type=event_type,
        event_id=event_id,
        payload=payload,
        headers=dict(request.headers),
        status='pending'
    )
    
    # Process event asynchronously
    from .tasks import process_stripe_webhook
    process_stripe_webhook.delay(webhook_event.id)
    
    return HttpResponse(status=200)
