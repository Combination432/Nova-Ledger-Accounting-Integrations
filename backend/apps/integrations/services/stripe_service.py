"""
Stripe integration service for Nova Ledger.
Handles transaction sync and detailed fee breakdown.
"""
import stripe
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from apps.transactions.models import Transaction, Fee, BankTransaction
from apps.integrations.models import Integration, SyncLog
from apps.accounts.models import ChartOfAccounts
import logging

logger = logging.getLogger(__name__)


class StripeIntegrationService:
    """
    Service for syncing Stripe payments and payouts with detailed fee breakdown.
    This is a key differentiator - Nova Ledger breaks down every fee component.
    """

    def __init__(self, integration: Integration):
        self.integration = integration
        self.organization = integration.organization

        # Initialize Stripe API
        api_key = integration.oauth_access_token or integration.auth_credentials.get('api_key')
        if not api_key:
            raise ValueError("Stripe API key is required")

        stripe.api_key = api_key

    def sync_charges(self, start_date=None, end_date=None):
        """
        Sync Stripe charges (payments) with detailed fee breakdown.
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='stripe_charges',
            status='running'
        )

        try:
            # Default to last 30 days
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()

            # Convert to Unix timestamps
            created_gte = int(start_date.timestamp())
            created_lte = int(end_date.timestamp())

            # Fetch charges from Stripe
            charges = stripe.Charge.list(
                limit=100,
                created={'gte': created_gte, 'lte': created_lte}
            )

            processed_count = 0
            created_count = 0
            updated_count = 0
            failed_count = 0

            for charge in charges.auto_paging_iter():
                try:
                    transaction = self._process_charge(charge)
                    processed_count += 1

                    if transaction:
                        created_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    logger.error(f"Failed to process Stripe charge {charge.id}: {str(e)}")
                    failed_count += 1

            # Update sync log
            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = processed_count
            sync_log.records_created = created_count
            sync_log.records_updated = updated_count
            sync_log.records_failed = failed_count
            sync_log.save()

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

    def _process_charge(self, charge):
        """
        Process a Stripe charge into a Nova Ledger transaction.
        """
        external_id = f"stripe_charge_{charge.id}"

        # Determine if this is a refund
        transaction_type = 'refund' if charge.refunded else 'payment'

        # Calculate amounts (Stripe amounts are in cents)
        gross_amount = Decimal(charge.amount) / 100
        fee_amount = Decimal(charge.balance_transaction.fee if charge.balance_transaction else 0) / 100
        net_amount = Decimal(charge.balance_transaction.net if charge.balance_transaction else charge.amount) / 100

        transaction, created = Transaction.objects.get_or_create(
            organization=self.organization,
            external_id=external_id,
            source_platform='stripe',
            defaults={
                'transaction_number': f"STRIPE-{charge.id[-8:]}",
                'transaction_type': transaction_type,
                'transaction_date': datetime.fromtimestamp(charge.created, tz=timezone.utc),
                'description': charge.description or f"Stripe Charge {charge.id}",
                'gross_amount': gross_amount,
                'net_amount': net_amount,
                'currency': charge.currency.upper(),
                'customer_name': charge.billing_details.name if charge.billing_details else "",
                'customer_email': charge.billing_details.email if charge.billing_details else "",
                'customer_id': charge.customer or "",
                'raw_data': charge.to_dict(),
            }
        )

        if not created:
            transaction.raw_data = charge.to_dict()
            transaction.save()

        # Process detailed fee breakdown
        if charge.balance_transaction:
            self._process_stripe_fees(transaction, charge.balance_transaction)

        return transaction if created else None

    def _process_stripe_fees(self, transaction, balance_transaction):
        """
        Break down Stripe fees into detailed components.
        This is a KEY DIFFERENTIATOR for Nova Ledger.
        """
        # Clear existing fees
        transaction.fees.all().delete()

        # Get or create fee accounts
        processing_fee_account = self._get_fee_account('payment_processing_fees', 'Payment Processing Fees')

        if isinstance(balance_transaction, str):
            # Fetch the balance transaction if we only have the ID
            balance_transaction = stripe.BalanceTransaction.retrieve(balance_transaction)

        # Total fee
        total_fee = Decimal(balance_transaction.fee) / 100

        # Fee breakdown
        fee_details = balance_transaction.fee_details

        for fee_detail in fee_details:
            fee_type = fee_detail.type
            fee_amount = Decimal(fee_detail.amount) / 100
            fee_description = fee_detail.description

            # Map Stripe fee types to Nova Ledger fee types
            fee_type_mapping = {
                'stripe_fee': 'payment_processing',
                'application_fee': 'platform_fee',
                'tax': 'transaction_fee',
            }

            nova_fee_type = fee_type_mapping.get(fee_type, 'other')

            Fee.objects.create(
                transaction=transaction,
                fee_type=nova_fee_type,
                fee_name=fee_description or f"Stripe {fee_type}",
                amount=fee_amount,
                expense_account=processing_fee_account,
                description=f"Stripe fee: {fee_description}"
            )

    def sync_payouts(self, start_date=None, end_date=None):
        """
        Sync Stripe payouts to bank account.
        """
        sync_log = SyncLog.objects.create(
            integration=self.integration,
            sync_type='stripe_payouts',
            status='running'
        )

        try:
            if not start_date:
                start_date = timezone.now() - timedelta(days=30)
            if not end_date:
                end_date = timezone.now()

            created_gte = int(start_date.timestamp())
            created_lte = int(end_date.timestamp())

            payouts = stripe.Payout.list(
                limit=100,
                created={'gte': created_gte, 'lte': created_lte}
            )

            processed_count = 0
            created_count = 0

            for payout in payouts.auto_paging_iter():
                try:
                    bank_transaction = self._process_payout(payout)
                    processed_count += 1
                    if bank_transaction:
                        created_count += 1

                except Exception as e:
                    logger.error(f"Failed to process Stripe payout {payout.id}: {str(e)}")

            sync_log.status = 'completed'
            sync_log.completed_at = timezone.now()
            sync_log.records_processed = processed_count
            sync_log.records_created = created_count
            sync_log.save()

            return sync_log

        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            raise

    def _process_payout(self, payout):
        """
        Process Stripe payout into bank transaction.
        """
        from apps.transactions.models import BankAccount

        # Try to find the default bank account
        bank_account = BankAccount.objects.filter(
            organization=self.organization,
            is_active=True
        ).first()

        if not bank_account:
            logger.warning(f"No bank account found for payout {payout.id}")
            return None

        external_id = f"stripe_payout_{payout.id}"

        bank_transaction, created = BankTransaction.objects.get_or_create(
            organization=self.organization,
            external_id=external_id,
            defaults={
                'bank_account': bank_account,
                'transaction_date': datetime.fromtimestamp(payout.created, tz=timezone.utc).date(),
                'description': f"Stripe Payout {payout.id}",
                'amount': Decimal(payout.amount) / 100,
                'source_platform': 'stripe',
            }
        )

        return bank_transaction if created else None

    def _get_fee_account(self, account_subtype, account_name):
        """
        Get or create a fee account.
        """
        account, _ = ChartOfAccounts.objects.get_or_create(
            organization=self.organization,
            account_type='expense',
            account_subtype=account_subtype,
            defaults={
                'account_number': '6000',
                'account_name': account_name,
            }
        )
        return account

    def reconstruct_payout(self, payout_id):
        """
        Reconstruct a payout by breaking it down into component transactions.
        This is a key feature of Nova Ledger's "Gross Payout Reconstruction".
        """
        payout = stripe.Payout.retrieve(payout_id)

        # Fetch all balance transactions for this payout
        balance_transactions = stripe.BalanceTransaction.list(
            payout=payout_id,
            limit=100
        )

        reconstruction = {
            'payout_id': payout_id,
            'payout_amount': Decimal(payout.amount) / 100,
            'currency': payout.currency.upper(),
            'arrival_date': datetime.fromtimestamp(payout.arrival_date, tz=timezone.utc).date(),
            'components': []
        }

        for bt in balance_transactions.auto_paging_iter():
            component = {
                'type': bt.type,
                'description': bt.description,
                'gross': Decimal(bt.amount) / 100,
                'fee': Decimal(bt.fee) / 100,
                'net': Decimal(bt.net) / 100,
                'source_id': bt.source,
            }
            reconstruction['components'].append(component)

        return reconstruction
