"""
Historical data import service.
Handles bulk import of historical transactions from platforms and CSV files.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db import transaction as db_transaction
from apps.transactions.models import Transaction
from ..models import Integration, SyncLog
import csv
import io
import logging

logger = logging.getLogger(__name__)


class HistoricalImportService:
    """
    Service for importing historical transaction data.
    """

    def __init__(self, integration: Integration):
        """
        Initialize historical import service.

        Args:
            integration: Integration to import data for
        """
        self.integration = integration
        self.organization = integration.organization

    def import_historical_from_platform(
        self,
        start_date: date,
        end_date: date,
        batch_size: int = 100
    ) -> Dict:
        """
        Import historical data from integrated platform.

        Args:
            start_date: Start date for import
            end_date: End date for import
            batch_size: Number of records to process per batch

        Returns:
            Dict with import results
        """
        platform = self.integration.integration_type

        if platform == 'shopify':
            return self._import_shopify_historical(start_date, end_date, batch_size)
        elif platform == 'stripe':
            return self._import_stripe_historical(start_date, end_date, batch_size)
        elif platform == 'quickbooks':
            return self._import_quickbooks_historical(start_date, end_date, batch_size)
        else:
            raise ValueError(f"Historical import not supported for {platform}")

    def _import_shopify_historical(
        self,
        start_date: date,
        end_date: date,
        batch_size: int
    ) -> Dict:
        """
        Import historical Shopify orders.
        """
        from .shopify_service import ShopifyIntegrationService
        from ..sync_engine import SyncEngine

        shopify_service = ShopifyIntegrationService(self.integration)
        sync_engine = SyncEngine(self.integration)

        # Create sync log
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='historical_import',
            status='in_progress',
            started_at=timezone.now()
        )

        results = {
            'platform': 'shopify',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        try:
            # Import orders in date range
            current_date = start_date

            while current_date <= end_date:
                # Process one month at a time
                month_end = min(
                    current_date + timedelta(days=30),
                    end_date
                )

                logger.info(f"Importing Shopify orders from {current_date} to {month_end}")

                try:
                    # Fetch orders for this period
                    orders = shopify_service.sync_orders(
                        start_date=current_date,
                        end_date=month_end
                    )

                    for order_data in orders:
                        try:
                            # Check if transaction already exists
                            existing = Transaction.objects.filter(
                                organization=self.organization,
                                source_platform='shopify',
                                source_id=order_data['transaction']['source_id']
                            ).first()

                            if existing:
                                # Update existing transaction
                                sync_engine._update_transaction(existing, order_data)
                                results['updated'] += 1
                            else:
                                # Create new transaction
                                sync_engine._create_transaction(order_data)
                                results['imported'] += 1

                        except Exception as e:
                            logger.error(f"Failed to import Shopify order: {str(e)}")
                            results['errors'] += 1
                            results['error_details'].append({
                                'order_id': order_data.get('transaction', {}).get('source_id'),
                                'error': str(e)
                            })

                except Exception as e:
                    logger.error(f"Failed to fetch Shopify orders for period: {str(e)}")
                    results['errors'] += 1
                    results['error_details'].append({
                        'period': f"{current_date} to {month_end}",
                        'error': str(e)
                    })

                current_date = month_end + timedelta(days=1)

            # Update sync log
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_synced = results['imported'] + results['updated']
            sync_log.save()

        except Exception as e:
            logger.error(f"Historical import failed: {str(e)}")
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

        return results

    def _import_stripe_historical(
        self,
        start_date: date,
        end_date: date,
        batch_size: int
    ) -> Dict:
        """
        Import historical Stripe charges and payments.
        """
        from .stripe_service import StripeIntegrationService
        from ..sync_engine import SyncEngine

        stripe_service = StripeIntegrationService(self.integration)
        sync_engine = SyncEngine(self.integration)

        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='historical_import',
            status='in_progress',
            started_at=timezone.now()
        )

        results = {
            'platform': 'stripe',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        try:
            # Import charges
            charges = stripe_service.sync_charges(
                start_date=start_date,
                end_date=end_date
            )

            for charge_data in charges:
                try:
                    existing = Transaction.objects.filter(
                        organization=self.organization,
                        source_platform='stripe',
                        source_id=charge_data['transaction']['source_id']
                    ).first()

                    if existing:
                        sync_engine._update_transaction(existing, charge_data)
                        results['updated'] += 1
                    else:
                        sync_engine._create_transaction(charge_data)
                        results['imported'] += 1

                except Exception as e:
                    logger.error(f"Failed to import Stripe charge: {str(e)}")
                    results['errors'] += 1
                    results['error_details'].append({
                        'charge_id': charge_data.get('transaction', {}).get('source_id'),
                        'error': str(e)
                    })

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_synced = results['imported'] + results['updated']
            sync_log.save()

        except Exception as e:
            logger.error(f"Historical import failed: {str(e)}")
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

        return results

    def _import_quickbooks_historical(
        self,
        start_date: date,
        end_date: date,
        batch_size: int
    ) -> Dict:
        """
        Import historical QuickBooks invoices and payments.
        """
        from .quickbooks_service import QuickBooksIntegrationService
        from ..sync_engine import SyncEngine

        qb_service = QuickBooksIntegrationService(self.integration)
        sync_engine = SyncEngine(self.integration)

        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='historical_import',
            status='in_progress',
            started_at=timezone.now()
        )

        results = {
            'platform': 'quickbooks',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        try:
            # Import invoices
            invoices = qb_service.sync_invoices(
                start_date=start_date,
                end_date=end_date,
                incremental=False
            )

            for invoice_data in invoices:
                try:
                    existing = Transaction.objects.filter(
                        organization=self.organization,
                        source_platform='quickbooks',
                        source_id=invoice_data['transaction']['source_id']
                    ).first()

                    if existing:
                        sync_engine._update_transaction(existing, invoice_data)
                        results['updated'] += 1
                    else:
                        sync_engine._create_transaction(invoice_data)
                        results['imported'] += 1

                except Exception as e:
                    logger.error(f"Failed to import QuickBooks invoice: {str(e)}")
                    results['errors'] += 1
                    results['error_details'].append({
                        'invoice_id': invoice_data.get('transaction', {}).get('source_id'),
                        'error': str(e)
                    })

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_synced = results['imported'] + results['updated']
            sync_log.save()

        except Exception as e:
            logger.error(f"Historical import failed: {str(e)}")
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

        return results

    def import_from_csv(
        self,
        csv_file,
        field_mapping: Optional[Dict] = None
    ) -> Dict:
        """
        Import transactions from CSV file.

        Args:
            csv_file: File object or path to CSV file
            field_mapping: Optional mapping of CSV columns to transaction fields

        Returns:
            Dict with import results
        """
        # Default field mapping
        default_mapping = {
            'date': 'transaction_date',
            'description': 'description',
            'amount': 'gross_amount',
            'type': 'transaction_type',
            'customer': 'customer_name',
            'category': 'category',
            'tax': 'tax_amount',
            'fees': 'fee_amount',
            'currency': 'currency'
        }

        mapping = field_mapping or default_mapping

        results = {
            'imported': 0,
            'skipped': 0,
            'errors': 0,
            'error_details': []
        }

        try:
            # Read CSV file
            if hasattr(csv_file, 'read'):
                content = csv_file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                csv_reader = csv.DictReader(io.StringIO(content))
            else:
                with open(csv_file, 'r') as f:
                    csv_reader = csv.DictReader(f)

            with db_transaction.atomic():
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        # Map CSV row to transaction data
                        txn_data = self._map_csv_row(row, mapping)

                        # Create transaction
                        transaction = Transaction.objects.create(
                            organization=self.organization,
                            source_platform='csv_import',
                            **txn_data
                        )

                        results['imported'] += 1

                    except Exception as e:
                        logger.error(f"Failed to import CSV row {row_num}: {str(e)}")
                        results['errors'] += 1
                        results['error_details'].append({
                            'row': row_num,
                            'data': dict(row),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"CSV import failed: {str(e)}")
            raise

        return results

    def _map_csv_row(self, row: Dict, mapping: Dict) -> Dict:
        """
        Map CSV row to transaction data.

        Args:
            row: CSV row as dict
            mapping: Field mapping

        Returns:
            Transaction data dict
        """
        txn_data = {}

        # Map each field
        for csv_field, txn_field in mapping.items():
            if csv_field in row and row[csv_field]:
                value = row[csv_field].strip()

                # Type conversion
                if txn_field == 'transaction_date':
                    # Try multiple date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            txn_data[txn_field] = datetime.strptime(value, fmt).date()
                            break
                        except ValueError:
                            continue

                elif txn_field in ['gross_amount', 'net_amount', 'tax_amount', 'fee_amount']:
                    # Clean and convert to Decimal
                    clean_value = value.replace(',', '').replace('$', '').strip()
                    txn_data[txn_field] = Decimal(clean_value)

                elif txn_field == 'transaction_type':
                    # Normalize transaction type
                    type_mapping = {
                        'sale': 'sale',
                        'income': 'sale',
                        'revenue': 'sale',
                        'expense': 'expense',
                        'payment': 'expense',
                        'refund': 'refund',
                        'transfer': 'transfer'
                    }
                    txn_data[txn_field] = type_mapping.get(value.lower(), 'sale')

                else:
                    txn_data[txn_field] = value

        # Set defaults
        if 'transaction_date' not in txn_data:
            txn_data['transaction_date'] = timezone.now().date()

        if 'transaction_type' not in txn_data:
            txn_data['transaction_type'] = 'sale'

        if 'gross_amount' not in txn_data:
            raise ValueError("Amount is required")

        # Calculate net amount if not provided
        if 'net_amount' not in txn_data:
            tax = txn_data.get('tax_amount', Decimal('0'))
            txn_data['net_amount'] = txn_data['gross_amount'] - tax

        return txn_data

    def validate_import_data(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Validate that import data doesn't overlap with existing data.

        Args:
            start_date: Proposed import start date
            end_date: Proposed import end date

        Returns:
            Dict with validation results
        """
        # Check for existing transactions in date range
        existing = Transaction.objects.filter(
            organization=self.organization,
            source_platform=self.integration.integration_type,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).count()

        # Get earliest and latest sync dates
        earliest_sync = Transaction.objects.filter(
            organization=self.organization,
            source_platform=self.integration.integration_type
        ).order_by('transaction_date').first()

        latest_sync = Transaction.objects.filter(
            organization=self.organization,
            source_platform=self.integration.integration_type
        ).order_by('-transaction_date').first()

        return {
            'is_valid': True,
            'existing_transactions': existing,
            'has_overlap': existing > 0,
            'earliest_existing_date': earliest_sync.transaction_date.isoformat() if earliest_sync else None,
            'latest_existing_date': latest_sync.transaction_date.isoformat() if latest_sync else None,
            'warning': f"Found {existing} existing transactions in date range" if existing > 0 else None
        }
