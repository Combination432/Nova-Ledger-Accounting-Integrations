"""
Automated journal entry generation service.
Converts transactions into proper double-entry bookkeeping journal entries.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date
from django.db.models import Q
from django.utils import timezone
from apps.transactions.models import Transaction
from apps.accounts.models import ChartOfAccounts
import logging

logger = logging.getLogger(__name__)


class JournalEntryService:
    """
    Service for automatically generating journal entries from transactions.
    Implements proper double-entry bookkeeping with debits and credits.
    """

    def __init__(self, organization):
        """
        Initialize journal entry service.

        Args:
            organization: Organization object
        """
        self.organization = organization
        self.base_currency = 'USD'  # Could be configurable

    def generate_journal_entry(
        self,
        transaction: Transaction,
        accounting_method: str = 'accrual'
    ) -> Dict:
        """
        Generate journal entry for a transaction.

        Args:
            transaction: Transaction to create journal entry for
            accounting_method: 'accrual' or 'cash'

        Returns:
            Dict with journal entry data
        """
        # Determine transaction type and generate appropriate entries
        if transaction.transaction_type == 'sale':
            return self._generate_sale_entry(transaction, accounting_method)
        elif transaction.transaction_type == 'refund':
            return self._generate_refund_entry(transaction, accounting_method)
        elif transaction.transaction_type == 'expense':
            return self._generate_expense_entry(transaction, accounting_method)
        elif transaction.transaction_type == 'transfer':
            return self._generate_transfer_entry(transaction)
        elif transaction.transaction_type == 'payout':
            return self._generate_payout_entry(transaction)
        else:
            logger.warning(f"Unknown transaction type: {transaction.transaction_type}")
            return self._generate_generic_entry(transaction)

    def _generate_sale_entry(
        self,
        transaction: Transaction,
        accounting_method: str
    ) -> Dict:
        """
        Generate journal entry for a sale transaction.

        Accrual method:
        DR Accounts Receivable (or Cash if paid)
        CR Sales Revenue
        CR Sales Tax Payable
        DR Payment Processing Fees
        CR Accounts Receivable (fee amount)

        Cash method:
        DR Cash
        CR Sales Revenue
        CR Sales Tax Payable
        DR Payment Processing Fees
        CR Cash (fee amount)
        """
        entries = []

        # Get or create accounts
        revenue_account = self._get_or_create_account(
            account_type='revenue',
            account_subtype='sales',
            account_name='Sales Revenue',
            account_number='4000'
        )

        tax_payable_account = self._get_or_create_account(
            account_type='liability',
            account_subtype='sales_tax_payable',
            account_name='Sales Tax Payable',
            account_number='2200'
        )

        fees_expense_account = self._get_or_create_account(
            account_type='expense',
            account_subtype='payment_processing',
            account_name='Payment Processing Fees',
            account_number='6200'
        )

        # Determine if cash or accrual
        is_paid = transaction.metadata.get('status') == 'paid'

        if accounting_method == 'cash' and not is_paid:
            # Don't record revenue until cash is received
            logger.info(f"Skipping journal entry for unpaid transaction {transaction.id} (cash method)")
            return {'entries': [], 'method': 'cash', 'status': 'deferred'}

        # Choose receivable or cash account
        if accounting_method == 'accrual' and not is_paid:
            debit_account = self._get_or_create_account(
                account_type='asset',
                account_subtype='accounts_receivable',
                account_name='Accounts Receivable',
                account_number='1200'
            )
        else:
            # Cash method or paid transaction
            # Try to get specific payment method account
            payment_method = transaction.metadata.get('payment_method', 'cash')
            debit_account = self._get_payment_account(payment_method)

        # DR Accounts Receivable / Cash (gross amount)
        entries.append({
            'account': debit_account.id,
            'account_name': debit_account.account_name,
            'account_number': debit_account.account_number,
            'debit': float(transaction.gross_amount),
            'credit': 0,
            'description': f"Sale - {transaction.description or transaction.customer_name or 'Unknown'}"
        })

        # CR Sales Revenue (net amount)
        entries.append({
            'account': revenue_account.id,
            'account_name': revenue_account.account_name,
            'account_number': revenue_account.account_number,
            'debit': 0,
            'credit': float(transaction.net_amount),
            'description': f"Sale - {transaction.description or 'Revenue'}"
        })

        # CR Sales Tax Payable (tax amount)
        if transaction.tax_amount and transaction.tax_amount > 0:
            entries.append({
                'account': tax_payable_account.id,
                'account_name': tax_payable_account.account_name,
                'account_number': tax_payable_account.account_number,
                'debit': 0,
                'credit': float(transaction.tax_amount),
                'description': f"Sales tax collected - {transaction.metadata.get('tax_jurisdiction', 'N/A')}"
            })

        # DR Payment Processing Fees, CR Cash/Receivable (fee amount)
        if transaction.fee_amount and transaction.fee_amount > 0:
            entries.append({
                'account': fees_expense_account.id,
                'account_name': fees_expense_account.account_name,
                'account_number': fees_expense_account.account_number,
                'debit': float(transaction.fee_amount),
                'credit': 0,
                'description': f"Processing fees - {transaction.source_platform}"
            })

            entries.append({
                'account': debit_account.id,
                'account_name': debit_account.account_name,
                'account_number': debit_account.account_number,
                'debit': 0,
                'credit': float(transaction.fee_amount),
                'description': f"Processing fees deduction"
            })

        return {
            'transaction_id': str(transaction.id),
            'transaction_date': transaction.transaction_date.isoformat(),
            'accounting_method': accounting_method,
            'entries': entries,
            'total_debits': sum(e['debit'] for e in entries),
            'total_credits': sum(e['credit'] for e in entries),
            'is_balanced': abs(sum(e['debit'] for e in entries) - sum(e['credit'] for e in entries)) < 0.01
        }

    def _generate_refund_entry(
        self,
        transaction: Transaction,
        accounting_method: str
    ) -> Dict:
        """
        Generate journal entry for a refund transaction.

        DR Sales Revenue
        DR Sales Tax Payable
        CR Cash / Accounts Receivable
        """
        entries = []

        revenue_account = self._get_or_create_account(
            account_type='revenue',
            account_subtype='sales',
            account_name='Sales Revenue',
            account_number='4000'
        )

        tax_payable_account = self._get_or_create_account(
            account_type='liability',
            account_subtype='sales_tax_payable',
            account_name='Sales Tax Payable',
            account_number='2200'
        )

        payment_method = transaction.metadata.get('payment_method', 'cash')
        credit_account = self._get_payment_account(payment_method)

        # DR Sales Revenue (reverse revenue)
        entries.append({
            'account': revenue_account.id,
            'account_name': revenue_account.account_name,
            'account_number': revenue_account.account_number,
            'debit': float(transaction.net_amount),
            'credit': 0,
            'description': f"Refund - {transaction.description or 'Revenue reversal'}"
        })

        # DR Sales Tax Payable (reverse tax)
        if transaction.tax_amount and transaction.tax_amount > 0:
            entries.append({
                'account': tax_payable_account.id,
                'account_name': tax_payable_account.account_name,
                'account_number': tax_payable_account.account_number,
                'debit': float(transaction.tax_amount),
                'credit': 0,
                'description': f"Refund - Tax reversal"
            })

        # CR Cash (refund payment)
        entries.append({
            'account': credit_account.id,
            'account_name': credit_account.account_name,
            'account_number': credit_account.account_number,
            'debit': 0,
            'credit': float(transaction.gross_amount),
            'description': f"Refund issued - {transaction.customer_name or 'Customer'}"
        })

        return {
            'transaction_id': str(transaction.id),
            'transaction_date': transaction.transaction_date.isoformat(),
            'accounting_method': accounting_method,
            'entries': entries,
            'total_debits': sum(e['debit'] for e in entries),
            'total_credits': sum(e['credit'] for e in entries),
            'is_balanced': abs(sum(e['debit'] for e in entries) - sum(e['credit'] for e in entries)) < 0.01
        }

    def _generate_expense_entry(
        self,
        transaction: Transaction,
        accounting_method: str
    ) -> Dict:
        """
        Generate journal entry for an expense transaction.

        DR Expense Account
        DR Input VAT/Tax (if applicable)
        CR Cash / Accounts Payable
        """
        entries = []

        # Determine expense category
        category = transaction.category or transaction.metadata.get('category', 'general')

        expense_account = self._get_expense_account(category)

        # Determine if cash or accrual
        is_paid = transaction.metadata.get('status') == 'paid'

        if accounting_method == 'cash' and not is_paid:
            logger.info(f"Skipping journal entry for unpaid expense {transaction.id} (cash method)")
            return {'entries': [], 'method': 'cash', 'status': 'deferred'}

        # Choose payable or cash account
        if accounting_method == 'accrual' and not is_paid:
            credit_account = self._get_or_create_account(
                account_type='liability',
                account_subtype='accounts_payable',
                account_name='Accounts Payable',
                account_number='2100'
            )
        else:
            payment_method = transaction.metadata.get('payment_method', 'cash')
            credit_account = self._get_payment_account(payment_method)

        # DR Expense (net amount)
        entries.append({
            'account': expense_account.id,
            'account_name': expense_account.account_name,
            'account_number': expense_account.account_number,
            'debit': float(transaction.net_amount),
            'credit': 0,
            'description': f"Expense - {transaction.description or category}"
        })

        # DR Input VAT/Tax (if reclaimable)
        if transaction.tax_amount and transaction.tax_amount > 0:
            is_reclaimable = transaction.metadata.get('vat_reclaimable', False)

            if is_reclaimable:
                input_vat_account = self._get_or_create_account(
                    account_type='asset',
                    account_subtype='input_vat',
                    account_name='Input VAT Recoverable',
                    account_number='1300'
                )

                entries.append({
                    'account': input_vat_account.id,
                    'account_name': input_vat_account.account_name,
                    'account_number': input_vat_account.account_number,
                    'debit': float(transaction.tax_amount),
                    'credit': 0,
                    'description': f"Input VAT - {transaction.description or 'Recoverable'}"
                })

        # CR Cash / Accounts Payable
        entries.append({
            'account': credit_account.id,
            'account_name': credit_account.account_name,
            'account_number': credit_account.account_number,
            'debit': 0,
            'credit': float(transaction.gross_amount),
            'description': f"Payment - {transaction.customer_name or 'Vendor'}"
        })

        return {
            'transaction_id': str(transaction.id),
            'transaction_date': transaction.transaction_date.isoformat(),
            'accounting_method': accounting_method,
            'entries': entries,
            'total_debits': sum(e['debit'] for e in entries),
            'total_credits': sum(e['credit'] for e in entries),
            'is_balanced': abs(sum(e['debit'] for e in entries) - sum(e['credit'] for e in entries)) < 0.01
        }

    def _generate_transfer_entry(self, transaction: Transaction) -> Dict:
        """
        Generate journal entry for a transfer between accounts.

        DR Destination Account
        CR Source Account
        """
        entries = []

        from_account_id = transaction.metadata.get('from_account')
        to_account_id = transaction.metadata.get('to_account')

        if not from_account_id or not to_account_id:
            logger.error(f"Transfer transaction {transaction.id} missing account information")
            return {'entries': [], 'error': 'Missing account information'}

        try:
            from_account = ChartOfAccounts.objects.get(id=from_account_id, organization=self.organization)
            to_account = ChartOfAccounts.objects.get(id=to_account_id, organization=self.organization)

            # DR Destination Account
            entries.append({
                'account': to_account.id,
                'account_name': to_account.account_name,
                'account_number': to_account.account_number,
                'debit': float(transaction.gross_amount),
                'credit': 0,
                'description': f"Transfer from {from_account.account_name}"
            })

            # CR Source Account
            entries.append({
                'account': from_account.id,
                'account_name': from_account.account_name,
                'account_number': from_account.account_number,
                'debit': 0,
                'credit': float(transaction.gross_amount),
                'description': f"Transfer to {to_account.account_name}"
            })

        except ChartOfAccounts.DoesNotExist as e:
            logger.error(f"Account not found for transfer: {str(e)}")
            return {'entries': [], 'error': 'Account not found'}

        return {
            'transaction_id': str(transaction.id),
            'transaction_date': transaction.transaction_date.isoformat(),
            'accounting_method': 'cash',
            'entries': entries,
            'total_debits': sum(e['debit'] for e in entries),
            'total_credits': sum(e['credit'] for e in entries),
            'is_balanced': abs(sum(e['debit'] for e in entries) - sum(e['credit'] for e in entries)) < 0.01
        }

    def _generate_payout_entry(self, transaction: Transaction) -> Dict:
        """
        Generate journal entry for a payout (platform to bank).

        DR Bank Account
        CR Clearing Account (or Stripe/Platform account)
        """
        entries = []

        bank_account = self._get_or_create_account(
            account_type='asset',
            account_subtype='bank',
            account_name='Business Checking Account',
            account_number='1000'
        )

        # Platform clearing account (e.g., Stripe account)
        platform = transaction.source_platform or 'platform'
        clearing_account = self._get_or_create_account(
            account_type='asset',
            account_subtype='clearing',
            account_name=f'{platform.title()} Clearing Account',
            account_number='1150'
        )

        # DR Bank Account
        entries.append({
            'account': bank_account.id,
            'account_name': bank_account.account_name,
            'account_number': bank_account.account_number,
            'debit': float(transaction.gross_amount),
            'credit': 0,
            'description': f"Payout from {platform}"
        })

        # CR Clearing Account
        entries.append({
            'account': clearing_account.id,
            'account_name': clearing_account.account_name,
            'account_number': clearing_account.account_number,
            'debit': 0,
            'credit': float(transaction.gross_amount),
            'description': f"Payout to bank"
        })

        return {
            'transaction_id': str(transaction.id),
            'transaction_date': transaction.transaction_date.isoformat(),
            'accounting_method': 'cash',
            'entries': entries,
            'total_debits': sum(e['debit'] for e in entries),
            'total_credits': sum(e['credit'] for e in entries),
            'is_balanced': abs(sum(e['debit'] for e in entries) - sum(e['credit'] for e in entries)) < 0.01
        }

    def _generate_generic_entry(self, transaction: Transaction) -> Dict:
        """
        Generate generic journal entry when transaction type is unknown.
        """
        logger.warning(f"Generating generic journal entry for transaction {transaction.id}")

        return {
            'transaction_id': str(transaction.id),
            'entries': [],
            'error': 'Unknown transaction type',
            'requires_manual_entry': True
        }

    def _get_or_create_account(
        self,
        account_type: str,
        account_subtype: str,
        account_name: str,
        account_number: str
    ) -> ChartOfAccounts:
        """
        Get or create a chart of accounts entry.
        """
        account, created = ChartOfAccounts.objects.get_or_create(
            organization=self.organization,
            account_number=account_number,
            defaults={
                'account_type': account_type,
                'account_subtype': account_subtype,
                'account_name': account_name,
                'is_active': True
            }
        )

        if created:
            logger.info(f"Created account: {account_name} ({account_number})")

        return account

    def _get_payment_account(self, payment_method: str) -> ChartOfAccounts:
        """
        Get appropriate cash/bank account for payment method.
        """
        payment_accounts = {
            'cash': ('1010', 'Cash'),
            'credit_card': ('1020', 'Credit Card Clearing'),
            'bank_transfer': ('1000', 'Business Checking Account'),
            'paypal': ('1030', 'PayPal Account'),
            'stripe': ('1040', 'Stripe Account'),
            'shopify_payments': ('1050', 'Shopify Payments'),
        }

        account_number, account_name = payment_accounts.get(
            payment_method.lower(),
            ('1010', 'Cash')
        )

        return self._get_or_create_account(
            account_type='asset',
            account_subtype='bank',
            account_name=account_name,
            account_number=account_number
        )

    def _get_expense_account(self, category: str) -> ChartOfAccounts:
        """
        Get appropriate expense account for category.
        """
        expense_accounts = {
            'advertising': ('6100', 'Advertising & Marketing'),
            'office_supplies': ('6300', 'Office Supplies'),
            'software': ('6400', 'Software & Subscriptions'),
            'shipping': ('6500', 'Shipping & Delivery'),
            'professional_fees': ('6600', 'Professional Fees'),
            'rent': ('6700', 'Rent Expense'),
            'utilities': ('6800', 'Utilities'),
            'insurance': ('6900', 'Insurance'),
            'travel': ('7100', 'Travel & Entertainment'),
            'general': ('6000', 'General Expenses'),
        }

        account_number, account_name = expense_accounts.get(
            category.lower(),
            ('6000', 'General Expenses')
        )

        return self._get_or_create_account(
            account_type='expense',
            account_subtype=category.lower(),
            account_name=account_name,
            account_number=account_number
        )

    def batch_generate_journal_entries(
        self,
        start_date: date,
        end_date: date,
        accounting_method: str = 'accrual'
    ) -> Dict:
        """
        Generate journal entries for all transactions in a date range.

        Args:
            start_date: Start date
            end_date: End date
            accounting_method: 'accrual' or 'cash'

        Returns:
            Dict with generation results
        """
        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).order_by('transaction_date')

        results = {
            'total_transactions': transactions.count(),
            'successful': 0,
            'failed': 0,
            'deferred': 0,
            'entries': []
        }

        for txn in transactions:
            try:
                journal_entry = self.generate_journal_entry(txn, accounting_method)

                if journal_entry.get('error'):
                    results['failed'] += 1
                elif journal_entry.get('status') == 'deferred':
                    results['deferred'] += 1
                else:
                    results['successful'] += 1
                    results['entries'].append(journal_entry)

            except Exception as e:
                logger.error(f"Failed to generate journal entry for transaction {txn.id}: {str(e)}")
                results['failed'] += 1

        return results
