"""
Real-time sync engine for platform integrations.
Core synchronization logic for all supported platforms.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from celery import shared_task
from celery.utils.log import get_task_logger
from .models import Integration, SyncLog, WebhookEvent
from .services import (
    ShopifyIntegrationService,
    StripeIntegrationService,
    QuickBooksIntegrationService
)
from apps.transactions.models import Transaction
import logging

logger = get_task_logger(__name__)


class SyncEngine:
    """
    Core synchronization engine that handles incremental syncs
    for all platform integrations.
    """

    PLATFORM_SERVICES = {
        'shopify': ShopifyIntegrationService,
        'stripe': StripeIntegrationService,
        'quickbooks': QuickBooksIntegrationService,
    }

    def __init__(self, integration: Integration):
        self.integration = integration
        self.organization = integration.organization
        self.service_class = self.PLATFORM_SERVICES.get(integration.integration_type)

        if not self.service_class:
            raise ValueError(f"Unsupported integration type: {integration.integration_type}")

        self.service = self.service_class(integration)

    def sync_transactions(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        force_full_sync: bool = False
    ) -> Dict[str, Any]:
        """
        Sync transactions from platform to Nova Ledger.

        Args:
            date_from: Start date for sync (None = use last sync)
            date_to: End date for sync (None = now)
            force_full_sync: If True, ignore last sync and sync everything

        Returns:
            Dict with sync results
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='manual' if force_full_sync else 'auto',
            status='running',
            started_at=timezone.now()
        )

        try:
            # Determine date range
            if not date_from:
                if force_full_sync:
                    date_from = self.integration.created_at
                else:
                    # Incremental sync - start from last successful sync
                    last_sync = SyncLog.objects.filter(
                        integration=self.integration,
                        status='success'
                    ).order_by('-completed_at').first()

                    if last_sync:
                        # Start 1 hour before last sync to catch late updates
                        date_from = last_sync.completed_at - timedelta(hours=1)
                    else:
                        # First sync - go back 30 days
                        date_from = timezone.now() - timedelta(days=30)

            if not date_to:
                date_to = timezone.now()

            logger.info(
                f"Starting sync for {self.integration.integration_type} "
                f"integration {self.integration.id} from {date_from} to {date_to}"
            )

            # Fetch transactions from platform
            platform_transactions = self.service.fetch_transactions(
                date_from=date_from,
                date_to=date_to
            )

            logger.info(f"Fetched {len(platform_transactions)} transactions from platform")

            # Process and import transactions
            imported_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            for platform_txn in platform_transactions:
                try:
                    result = self._import_transaction(platform_txn)

                    if result['action'] == 'created':
                        imported_count += 1
                    elif result['action'] == 'updated':
                        updated_count += 1
                    else:
                        skipped_count += 1

                except Exception as e:
                    logger.error(f"Error importing transaction: {str(e)}", exc_info=True)
                    errors.append({
                        'transaction_id': platform_txn.get('id'),
                        'error': str(e)
                    })

            # Update sync log
            sync_log.status = 'success' if not errors else 'partial'
            sync_log.records_created = imported_count
            sync_log.records_updated = updated_count
            sync_log.records_processed = imported_count + updated_count + skipped_count
            sync_log.completed_at = timezone.now()
            sync_log.error_details = errors if errors else {}
            sync_log.save()

            # Update integration last sync
            self.integration.last_sync_at = timezone.now()
            # Removed sync_status field if not errors else 'error'
            self.integration.save()

            result = {
                'status': 'success' if not errors else 'partial',
                'imported': imported_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': errors,
                'sync_log_id': str(sync_log.id)
            }

            logger.info(f"Sync completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Sync failed: {str(e)}", exc_info=True)

            sync_log.status = 'failed'
            sync_log.completed_at = timezone.now()
            sync_log.error_details = {'error': str(e)}
            sync_log.save()

            # Removed sync_status field
            self.integration.save()

            raise

    @transaction.atomic
    def _import_transaction(self, platform_data: Dict) -> Dict[str, str]:
        """
        Import a single transaction from platform data.

        Args:
            platform_data: Transaction data from platform

        Returns:
            Dict with action taken ('created', 'updated', 'skipped')
        """
        external_id = platform_data.get('id')

        # Check if transaction already exists
        existing = Transaction.objects.filter(
            organization=self.organization,
            external_transaction_id=external_id,
            source_platform=self.integration.integration_type
        ).first()

        # Parse platform data
        transaction_data = self._parse_platform_transaction(platform_data)

        if existing:
            # Check if update is needed
            if self._needs_update(existing, transaction_data):
                self._update_transaction(existing, transaction_data)
                return {'action': 'updated', 'transaction_id': str(existing.id)}
            else:
                return {'action': 'skipped', 'transaction_id': str(existing.id)}
        else:
            # Create new transaction
            txn = self._create_transaction(transaction_data)
            return {'action': 'created', 'transaction_id': str(txn.id)}

    def _parse_platform_transaction(self, platform_data: Dict) -> Dict:
        """
        Parse platform-specific transaction data into normalized format.

        Args:
            platform_data: Raw platform data

        Returns:
            Normalized transaction data
        """
        # Delegate to platform-specific service
        return self.service.parse_transaction(platform_data)

    def _needs_update(self, existing: Transaction, new_data: Dict) -> bool:
        """
        Check if existing transaction needs to be updated.

        Args:
            existing: Existing Transaction object
            new_data: New transaction data (with 'transaction' key)

        Returns:
            True if update is needed
        """
        # Extract transaction data
        txn_data = new_data.get('transaction', {})

        # Check if key fields have changed
        if existing.gross_amount != txn_data.get('gross_amount'):
            return True
        if existing.net_amount != txn_data.get('net_amount'):
            return True
        if existing.transaction_type != txn_data.get('transaction_type'):
            return True

        # Check if status changed (e.g., pending -> completed)
        platform_status = txn_data.get('metadata', {}).get('status')
        existing_status = existing.metadata.get('status') if existing.metadata else None

        if platform_status != existing_status:
            return True

        return False

    def _create_transaction(self, data: Dict) -> Transaction:
        """
        Create a new transaction from parsed data.

        Args:
            data: Normalized transaction data

        Returns:
            Created Transaction object
        """
        from apps.transactions.models import Fee, TransactionLineItem

        # Create transaction
        txn = Transaction.objects.create(
            organization=self.organization,
            source_platform=self.integration.integration_type,
            **data['transaction']
        )

        # Create fees
        for fee_data in data.get('fees', []):
            Fee.objects.create(transaction=txn, **fee_data)

        # Create line items
        for item_data in data.get('line_items', []):
            TransactionLineItem.objects.create(transaction=txn, **item_data)

        logger.info(f"Created transaction {txn.id} from {self.integration.integration_type}")

        return txn

    def _update_transaction(self, txn: Transaction, data: Dict):
        """
        Update existing transaction with new data.

        Args:
            txn: Existing Transaction object
            data: New transaction data
        """
        # Update transaction fields
        for key, value in data['transaction'].items():
            setattr(txn, key, value)

        txn.save()

        logger.info(f"Updated transaction {txn.id}")

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync status for this integration.

        Returns:
            Dict with sync status information
        """
        last_sync = SyncLog.objects.filter(
            integration=self.integration
        ).order_by('-completed_at').first()

        if not last_sync:
            return {
                'status': 'never_synced',
                'last_sync_at': None,
                'next_sync_at': None
            }

        # Calculate next scheduled sync (every 15 minutes)
        next_sync = last_sync.completed_at + timedelta(minutes=15) if last_sync.completed_at else None

        return {
            'status': last_sync.status,
            'last_sync_at': last_sync.completed_at,
            'next_sync_at': next_sync,
            'records_processed': last_sync.records_processed,
            'records_created': last_sync.records_created,
            'records_updated': last_sync.records_updated,
            'error_details': last_sync.error_details
        }


class ConflictResolver:
    """
    Handles sync conflicts when same transaction is modified in multiple places.
    """

    @staticmethod
    def resolve_conflict(
        local_transaction: Transaction,
        remote_data: Dict,
        strategy: str = 'remote_wins'
    ) -> Transaction:
        """
        Resolve conflict between local and remote transaction data.

        Args:
            local_transaction: Local Transaction object
            remote_data: Remote transaction data
            strategy: Conflict resolution strategy
                - 'remote_wins': Always use remote data
                - 'local_wins': Keep local data
                - 'newest_wins': Use most recently updated
                - 'manual': Flag for manual resolution

        Returns:
            Resolved Transaction object
        """
        if strategy == 'remote_wins':
            # Update with remote data
            for key, value in remote_data.items():
                if hasattr(local_transaction, key):
                    setattr(local_transaction, key, value)
            local_transaction.save()

        elif strategy == 'local_wins':
            # Keep local data
            pass

        elif strategy == 'newest_wins':
            remote_updated_at = remote_data.get('updated_at')
            if remote_updated_at and remote_updated_at > local_transaction.updated_at:
                # Remote is newer
                for key, value in remote_data.items():
                    if hasattr(local_transaction, key):
                        setattr(local_transaction, key, value)
                local_transaction.save()

        elif strategy == 'manual':
            # Flag for manual review
            local_transaction.metadata = local_transaction.metadata or {}
            local_transaction.metadata['has_conflict'] = True
            local_transaction.metadata['remote_data'] = remote_data
            local_transaction.save()

        return local_transaction
