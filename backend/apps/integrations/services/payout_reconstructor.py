"""
Payout Reconstruction Service for Nova Ledger.
This is a KEY DIFFERENTIATOR: Breaking down gross payouts into component parts.

Automatically reconstructs bank deposits/payouts into:
- Sales Revenue
- Sales Tax Collected
- Payment Processing Fees
- Platform Fees (e.g., Amazon FBA fees)
- Refunds
- Chargebacks
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.transactions.models import (
    Transaction, Fee, BankTransaction, JournalEntry, JournalEntryLine
)
from apps.accounts.models import ChartOfAccounts
import logging

logger = logging.getLogger(__name__)


class PayoutReconstructionService:
    """
    Service for reconstructing gross payouts into detailed transaction components.
    """

    def __init__(self, organization):
        self.organization = organization

    @transaction.atomic
    def reconstruct_payout(self, bank_transaction_id):
        """
        Reconstruct a bank payout into its component transactions.

        Args:
            bank_transaction_id: UUID of the bank transaction (payout)

        Returns:
            dict: Reconstruction summary with all components
        """
        bank_transaction = BankTransaction.objects.get(
            id=bank_transaction_id,
            organization=self.organization
        )

        # Find all transactions that should be included in this payout
        # This depends on the source platform's payout logic
        if bank_transaction.source_platform == 'stripe':
            return self._reconstruct_stripe_payout(bank_transaction)
        elif bank_transaction.source_platform == 'shopify':
            return self._reconstruct_shopify_payout(bank_transaction)
        elif bank_transaction.source_platform == 'amazon':
            return self._reconstruct_amazon_payout(bank_transaction)
        else:
            return self._reconstruct_generic_payout(bank_transaction)

    def _reconstruct_stripe_payout(self, bank_transaction):
        """
        Reconstruct a Stripe payout.
        Stripe includes: charges - fees - refunds = payout
        """
        reconstruction = {
            'payout_id': str(bank_transaction.id),
            'payout_amount': bank_transaction.amount,
            'payout_date': bank_transaction.transaction_date,
            'components': {
                'gross_sales': Decimal('0.00'),
                'processing_fees': Decimal('0.00'),
                'refunds': Decimal('0.00'),
                'chargebacks': Decimal('0.00'),
                'other_fees': Decimal('0.00'),
            },
            'transactions': []
        }

        # Find all Stripe transactions around this payout date
        # Typically Stripe pays out T-2 (transactions from 2 days ago)
        payout_date = bank_transaction.transaction_date
        related_transactions = Transaction.objects.filter(
            organization=self.organization,
            source_platform='stripe',
            transaction_date__date=payout_date,
            is_reconciled=False
        )

        for txn in related_transactions:
            reconstruction['transactions'].append({
                'id': str(txn.id),
                'type': txn.transaction_type,
                'gross': txn.gross_amount,
                'net': txn.net_amount,
                'fees': txn.gross_amount - txn.net_amount,
            })

            # Aggregate components
            if txn.transaction_type == 'payment':
                reconstruction['components']['gross_sales'] += txn.gross_amount
                # Calculate fees
                for fee in txn.fees.all():
                    reconstruction['components']['processing_fees'] += fee.amount

            elif txn.transaction_type == 'refund':
                reconstruction['components']['refunds'] += abs(txn.gross_amount)

        # Calculate expected payout
        expected_payout = (
            reconstruction['components']['gross_sales']
            - reconstruction['components']['processing_fees']
            - reconstruction['components']['refunds']
            - reconstruction['components']['chargebacks']
            - reconstruction['components']['other_fees']
        )

        reconstruction['expected_payout'] = expected_payout
        reconstruction['variance'] = bank_transaction.amount - expected_payout
        reconstruction['is_balanced'] = abs(reconstruction['variance']) < Decimal('0.01')

        # If balanced, create journal entry
        if reconstruction['is_balanced']:
            journal_entry = self._create_payout_journal_entry(
                bank_transaction, reconstruction
            )
            reconstruction['journal_entry_id'] = str(journal_entry.id)

            # Mark transactions as reconciled
            related_transactions.update(
                is_reconciled=True,
                reconciliation_date=timezone.now(),
                bank_transaction=bank_transaction
            )

        return reconstruction

    def _reconstruct_shopify_payout(self, bank_transaction):
        """
        Reconstruct a Shopify payout.
        Shopify Payments includes: orders - fees - refunds - gateway fees = payout
        """
        reconstruction = {
            'payout_id': str(bank_transaction.id),
            'payout_amount': bank_transaction.amount,
            'components': {
                'gross_sales': Decimal('0.00'),
                'sales_tax': Decimal('0.00'),
                'shipping': Decimal('0.00'),
                'processing_fees': Decimal('0.00'),
                'platform_fees': Decimal('0.00'),
                'refunds': Decimal('0.00'),
            },
            'transactions': []
        }

        # Find related Shopify transactions
        payout_date = bank_transaction.transaction_date
        related_transactions = Transaction.objects.filter(
            organization=self.organization,
            source_platform='shopify',
            transaction_date__date=payout_date,
            is_reconciled=False
        )

        for txn in related_transactions:
            if txn.transaction_type == 'sale':
                reconstruction['components']['gross_sales'] += txn.gross_amount

                # Extract sales tax from line items
                for line_item in txn.line_items.all():
                    reconstruction['components']['sales_tax'] += line_item.tax_amount

                # Extract fees
                for fee in txn.fees.all():
                    if fee.fee_type == 'payment_processing':
                        reconstruction['components']['processing_fees'] += fee.amount
                    elif fee.fee_type == 'platform_fee':
                        reconstruction['components']['platform_fees'] += fee.amount
                    elif fee.fee_type == 'shipping_fee':
                        reconstruction['components']['shipping'] += fee.amount

            elif txn.transaction_type == 'refund':
                reconstruction['components']['refunds'] += abs(txn.gross_amount)

            reconstruction['transactions'].append({
                'id': str(txn.id),
                'type': txn.transaction_type,
                'amount': txn.gross_amount,
            })

        # Calculate expected payout
        expected_payout = (
            reconstruction['components']['gross_sales']
            - reconstruction['components']['processing_fees']
            - reconstruction['components']['platform_fees']
            - reconstruction['components']['refunds']
        )

        reconstruction['expected_payout'] = expected_payout
        reconstruction['variance'] = bank_transaction.amount - expected_payout
        reconstruction['is_balanced'] = abs(reconstruction['variance']) < Decimal('1.00')  # $1 tolerance

        return reconstruction

    def _reconstruct_amazon_payout(self, bank_transaction):
        """
        Reconstruct an Amazon Seller Central payout.
        Amazon is complex: sales - fees - FBA fees - refunds - reimbursements = payout
        """
        reconstruction = {
            'payout_id': str(bank_transaction.id),
            'payout_amount': bank_transaction.amount,
            'components': {
                'gross_sales': Decimal('0.00'),
                'amazon_fees': Decimal('0.00'),
                'fba_fees': Decimal('0.00'),
                'storage_fees': Decimal('0.00'),
                'refunds': Decimal('0.00'),
                'reimbursements': Decimal('0.00'),
            },
            'transactions': []
        }

        # Amazon settlement typically covers a specific date range
        # This would need integration with Amazon SP-API to get settlement report
        # For now, we'll create a placeholder

        logger.warning("Amazon payout reconstruction requires SP-API integration")

        return reconstruction

    def _reconstruct_generic_payout(self, bank_transaction):
        """
        Generic payout reconstruction for unknown platforms.
        """
        reconstruction = {
            'payout_id': str(bank_transaction.id),
            'payout_amount': bank_transaction.amount,
            'message': 'Generic reconstruction - manual review recommended'
        }

        return reconstruction

    def _create_payout_journal_entry(self, bank_transaction, reconstruction):
        """
        Create a journal entry for the reconstructed payout.

        Journal entry structure:
        DR Cash (Bank Account)           $X.XX
        DR Processing Fees Expense       $X.XX
        DR Platform Fees Expense         $X.XX
            CR Sales Revenue                  $X.XX
            CR Sales Tax Payable              $X.XX
        """
        # Get or create necessary accounts
        cash_account = self._get_account('asset', 'cash', 'Cash Account')
        revenue_account = self._get_account('revenue', 'sales_revenue', 'Sales Revenue')
        sales_tax_account = self._get_account('liability', 'sales_tax_payable', 'Sales Tax Payable')
        processing_fee_account = self._get_account('expense', 'payment_processing_fees', 'Payment Processing Fees')

        # Create journal entry
        journal_entry = JournalEntry.objects.create(
            organization=self.organization,
            entry_number=f"PAYOUT-{bank_transaction.id}",
            entry_date=bank_transaction.transaction_date,
            posting_date=bank_transaction.transaction_date,
            description=f"Payout Reconstruction: {bank_transaction.description}",
            status='posted'
        )

        # DR Cash
        JournalEntryLine.objects.create(
            journal_entry=journal_entry,
            account=cash_account,
            description=f"Payout deposit: {bank_transaction.description}",
            debit_amount=bank_transaction.amount,
            credit_amount=Decimal('0.00')
        )

        # DR Processing Fees
        processing_fees = reconstruction['components'].get('processing_fees', Decimal('0.00'))
        if processing_fees > 0:
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=processing_fee_account,
                description="Payment processing fees",
                debit_amount=processing_fees,
                credit_amount=Decimal('0.00')
            )

        # CR Sales Revenue
        gross_sales = reconstruction['components'].get('gross_sales', Decimal('0.00'))
        if gross_sales > 0:
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=revenue_account,
                description="Sales revenue",
                debit_amount=Decimal('0.00'),
                credit_amount=gross_sales
            )

        # CR Sales Tax Payable
        sales_tax = reconstruction['components'].get('sales_tax', Decimal('0.00'))
        if sales_tax > 0:
            JournalEntryLine.objects.create(
                journal_entry=journal_entry,
                account=sales_tax_account,
                description="Sales tax collected",
                debit_amount=Decimal('0.00'),
                credit_amount=sales_tax
            )

        return journal_entry

    def _get_account(self, account_type, account_subtype, account_name):
        """
        Get or create a chart of accounts entry.
        """
        account, _ = ChartOfAccounts.objects.get_or_create(
            organization=self.organization,
            account_type=account_type,
            account_subtype=account_subtype,
            defaults={
                'account_number': '1000',  # Would need proper numbering scheme
                'account_name': account_name,
            }
        )
        return account
