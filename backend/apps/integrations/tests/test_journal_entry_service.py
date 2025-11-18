"""
Tests for journal entry service.
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.transactions.models import Transaction
from apps.accounts.models import ChartOfAccounts
from apps.integrations.services.journal_entry_service import JournalEntryService

User = get_user_model()


class JournalEntryServiceTestCase(TestCase):
    """Test cases for JournalEntryService."""

    def setUp(self):
        """Set up test data."""
        # Create test user and organization
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.organization = self.user.organization

        # Create journal entry service
        self.service = JournalEntryService(self.organization)

        # Create test accounts
        self.revenue_account = ChartOfAccounts.objects.create(
            organization=self.organization,
            account_type='revenue',
            account_subtype='sales',
            account_number='4000',
            account_name='Sales Revenue'
        )

        self.cash_account = ChartOfAccounts.objects.create(
            organization=self.organization,
            account_type='asset',
            account_subtype='bank',
            account_number='1010',
            account_name='Cash'
        )

    def test_generate_sale_journal_entry(self):
        """Test generating journal entry for a sale."""
        # Create sale transaction
        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('92.59'),
            tax_amount=Decimal('7.41'),
            fee_amount=Decimal('2.90'),
            customer_name='Test Customer',
            description='Test Sale'
        )

        # Generate journal entry
        journal_entry = self.service.generate_journal_entry(transaction, 'cash')

        # Verify journal entry
        self.assertEqual(journal_entry['transaction_id'], str(transaction.id))
        self.assertIsNotNone(journal_entry['entries'])
        self.assertTrue(journal_entry['is_balanced'])
        self.assertEqual(
            journal_entry['total_debits'],
            journal_entry['total_credits']
        )

        # Verify entries contain expected accounts
        entries = journal_entry['entries']
        self.assertGreater(len(entries), 0)

    def test_generate_expense_journal_entry(self):
        """Test generating journal entry for an expense."""
        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='expense',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('50.00'),
            net_amount=Decimal('50.00'),
            category='office_supplies',
            description='Office Supplies Purchase',
            metadata={'status': 'paid'}
        )

        journal_entry = self.service.generate_journal_entry(transaction, 'cash')

        self.assertTrue(journal_entry['is_balanced'])
        self.assertEqual(
            journal_entry['total_debits'],
            journal_entry['total_credits']
        )

    def test_generate_refund_journal_entry(self):
        """Test generating journal entry for a refund."""
        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='refund',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('92.59'),
            tax_amount=Decimal('7.41'),
            customer_name='Test Customer',
            description='Refund for Order #123'
        )

        journal_entry = self.service.generate_journal_entry(transaction, 'cash')

        self.assertTrue(journal_entry['is_balanced'])
        self.assertGreater(len(journal_entry['entries']), 0)

    def test_journal_entry_balancing(self):
        """Test that journal entries are always balanced."""
        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('1000.00'),
            net_amount=Decimal('900.00'),
            tax_amount=Decimal('100.00'),
            description='Large Sale'
        )

        journal_entry = self.service.generate_journal_entry(transaction, 'accrual')

        # Verify debits equal credits
        self.assertTrue(journal_entry['is_balanced'])
        self.assertAlmostEqual(
            journal_entry['total_debits'],
            journal_entry['total_credits'],
            places=2
        )

    def test_accrual_vs_cash_accounting(self):
        """Test difference between accrual and cash accounting methods."""
        # Create unpaid transaction
        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('100.00'),
            description='Unpaid Invoice',
            metadata={'status': 'pending'}
        )

        # Test accrual method (should record)
        accrual_entry = self.service.generate_journal_entry(transaction, 'accrual')
        self.assertGreater(len(accrual_entry.get('entries', [])), 0)

        # Test cash method (should defer)
        cash_entry = self.service.generate_journal_entry(transaction, 'cash')
        self.assertEqual(cash_entry.get('status'), 'deferred')

    def test_batch_generate_journal_entries(self):
        """Test batch journal entry generation."""
        # Create multiple transactions
        for i in range(5):
            Transaction.objects.create(
                organization=self.organization,
                transaction_type='sale',
                transaction_date=date(2024, 1, 15 + i),
                gross_amount=Decimal('100.00') * (i + 1),
                net_amount=Decimal('90.00') * (i + 1),
                tax_amount=Decimal('10.00') * (i + 1),
                description=f'Sale {i+1}'
            )

        # Batch generate
        results = self.service.batch_generate_journal_entries(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            accounting_method='cash'
        )

        self.assertEqual(results['total_transactions'], 5)
        self.assertGreater(results['successful'], 0)

    def test_chart_of_accounts_auto_creation(self):
        """Test that missing chart of accounts are created automatically."""
        initial_count = ChartOfAccounts.objects.filter(
            organization=self.organization
        ).count()

        transaction = Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('100.00'),
            net_amount=Decimal('100.00'),
            description='Test Sale'
        )

        self.service.generate_journal_entry(transaction, 'cash')

        # Check that new accounts were created
        final_count = ChartOfAccounts.objects.filter(
            organization=self.organization
        ).count()

        self.assertGreater(final_count, initial_count)
