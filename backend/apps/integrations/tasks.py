"""
Celery tasks for integration processing and background sync operations.
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta
from .models import WebhookEvent, Integration, SyncLog
from .services import ShopifyIntegrationService, StripeIntegrationService
from .sync_engine import SyncEngine

logger = get_task_logger(__name__)


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


# ============================================================================
# Sync Engine Tasks - Real-time transaction synchronization
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_integration_transactions(self, integration_id: str, force_full_sync: bool = False):
    """
    Background task to sync transactions for a specific integration.

    Args:
        integration_id: UUID of the integration
        force_full_sync: Whether to perform full sync (default: incremental)

    Returns:
        Dict with sync results
    """
    try:
        integration = Integration.objects.get(id=integration_id)

        # Check if integration is active
        if not integration.is_active:
            logger.warning(f"Integration {integration_id} is not active, skipping sync")
            return {'status': 'skipped', 'reason': 'integration_inactive'}

        # Initialize sync engine
        engine = SyncEngine(integration)

        # Perform sync
        result = engine.sync_transactions(force_full_sync=force_full_sync)

        logger.info(f"Sync completed for integration {integration_id}: {result}")
        return result

    except Integration.DoesNotExist:
        logger.error(f"Integration {integration_id} not found")
        raise

    except Exception as e:
        logger.error(f"Sync failed for integration {integration_id}: {str(e)}", exc_info=True)

        # Retry with exponential backoff
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for integration {integration_id}")
            raise


@shared_task
def scheduled_sync_all_integrations():
    """
    Run scheduled sync for all active integrations.
    This task should be called by Celery Beat every 15 minutes.

    Returns:
        Dict with summary of sync operations
    """
    logger.info("Starting scheduled sync for all active integrations")

    # Get all active integrations
    integrations = Integration.objects.filter(is_active=True)

    total = integrations.count()
    queued = 0
    skipped = 0

    for integration in integrations:
        # Check if sync is needed (avoid too frequent syncs)
        last_sync = SyncLog.objects.filter(
            integration=integration
        ).order_by('-started_at').first()

        if last_sync:
            # Skip if last sync was less than 10 minutes ago
            time_since_sync = timezone.now() - last_sync.started_at
            if time_since_sync < timedelta(minutes=10):
                logger.debug(f"Skipping integration {integration.id} - synced {time_since_sync.seconds}s ago")
                skipped += 1
                continue

        # Queue sync task
        sync_integration_transactions.delay(str(integration.id))
        queued += 1

    result = {
        'total_integrations': total,
        'queued': queued,
        'skipped': skipped,
        'timestamp': timezone.now().isoformat()
    }

    logger.info(f"Scheduled sync completed: {result}")
    return result


@shared_task
def retry_failed_syncs():
    """
    Retry syncs that failed in the last 24 hours.
    This task should be called by Celery Beat every hour.

    Returns:
        Dict with retry summary
    """
    logger.info("Starting retry of failed syncs")

    # Find failed syncs from last 24 hours
    cutoff_time = timezone.now() - timedelta(hours=24)

    failed_syncs = SyncLog.objects.filter(
        status='failed',
        started_at__gte=cutoff_time,
        integration__is_active=True
    ).select_related('integration').distinct('integration')

    total = failed_syncs.count()
    queued = 0

    for sync_log in failed_syncs:
        integration = sync_log.integration

        # Check how many times we've retried
        retry_count = SyncLog.objects.filter(
            integration=integration,
            status='failed',
            started_at__gte=cutoff_time
        ).count()

        # Don't retry more than 5 times
        if retry_count >= 5:
            logger.warning(f"Integration {integration.id} has failed {retry_count} times, skipping retry")
            continue

        # Queue retry
        sync_integration_transactions.delay(str(integration.id))
        queued += 1

    result = {
        'total_failed': total,
        'queued': queued,
        'timestamp': timezone.now().isoformat()
    }

    logger.info(f"Failed sync retry completed: {result}")
    return result


@shared_task
def cleanup_old_sync_logs(days_to_keep: int = 90):
    """
    Clean up old sync logs to prevent database bloat.
    Keep only logs from the last N days (default: 90).

    Args:
        days_to_keep: Number of days of logs to retain

    Returns:
        Number of logs deleted
    """
    logger.info(f"Starting cleanup of sync logs older than {days_to_keep} days")

    cutoff_date = timezone.now() - timedelta(days=days_to_keep)

    # Delete old logs
    deleted_count, _ = SyncLog.objects.filter(
        started_at__lt=cutoff_date
    ).delete()

    logger.info(f"Deleted {deleted_count} old sync logs")
    return deleted_count
