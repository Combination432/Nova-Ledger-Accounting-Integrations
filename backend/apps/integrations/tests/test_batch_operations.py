"""
Tests for batch operations service.
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.transactions.models import Transaction
from apps.accounts.models import ChartOfAccounts
from apps.integrations.models import TransactionRule
from apps.integrations.services.batch_operations_service import BatchOperationsService

User = get_user_model()


class BatchOperationsServiceTestCase(TestCase):
    """Test cases for BatchOperationsService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.organization = self.user.organization
        self.service = BatchOperationsService(self.organization)

        # Create test account
        self.test_account = ChartOfAccounts.objects.create(
            organization=self.organization,
            account_type='expense',
            account_subtype='office_supplies',
            account_number='6300',
            account_name='Office Supplies'
        )

        # Create test transactions
        self.transactions = []
        for i in range(5):
            txn = Transaction.objects.create(
                organization=self.organization,
                transaction_type='expense',
                transaction_date=date(2024, 1, 15 + i),
                gross_amount=Decimal('50.00') * (i + 1),
                net_amount=Decimal('50.00') * (i + 1),
                description=f'Test Transaction {i+1}'
            )
            self.transactions.append(txn)

        self.transaction_ids = [str(txn.id) for txn in self.transactions]

    def test_batch_categorize(self):
        """Test batch categorization."""
        results = self.service.batch_categorize(
            self.transaction_ids,
            str(self.test_account.id)
        )

        self.assertEqual(results['updated'], 5)
        self.assertEqual(results['failed'], 0)

        # Verify transactions were categorized
        for txn in self.transactions:
            txn.refresh_from_db()
            self.assertEqual(txn.category, 'Office Supplies')

    def test_batch_tag_add(self):
        """Test adding tags in batch."""
        tags = ['urgent', 'reviewed']

        results = self.service.batch_tag(
            self.transaction_ids,
            tags,
            action='add'
        )

        self.assertEqual(results['updated'], 5)

        # Verify tags were added
        for txn in self.transactions:
            txn.refresh_from_db()
            txn_tags = txn.metadata.get('tags', [])
            self.assertIn('urgent', txn_tags)
            self.assertIn('reviewed', txn_tags)

    def test_batch_tag_remove(self):
        """Test removing tags in batch."""
        # First add tags
        for txn in self.transactions:
            txn.metadata = {'tags': ['urgent', 'reviewed', 'keep']}
            txn.save()

        # Remove some tags
        results = self.service.batch_tag(
            self.transaction_ids,
            ['urgent', 'reviewed'],
            action='remove'
        )

        self.assertEqual(results['updated'], 5)

        # Verify tags were removed
        for txn in self.transactions:
            txn.refresh_from_db()
            txn_tags = txn.metadata.get('tags', [])
            self.assertNotIn('urgent', txn_tags)
            self.assertNotIn('reviewed', txn_tags)
            self.assertIn('keep', txn_tags)

    def test_batch_update_fields(self):
        """Test updating fields in batch."""
        field_updates = {
            'customer_name': 'Bulk Customer',
            'category': 'Updated Category'
        }

        results = self.service.batch_update_fields(
            self.transaction_ids,
            field_updates
        )

        self.assertEqual(results['updated'], 5)

        # Verify fields were updated
        for txn in self.transactions:
            txn.refresh_from_db()
            self.assertEqual(txn.customer_name, 'Bulk Customer')
            self.assertEqual(txn.category, 'Updated Category')

    def test_batch_soft_delete(self):
        """Test soft delete in batch."""
        results = self.service.batch_delete(
            self.transaction_ids,
            soft_delete=True
        )

        self.assertEqual(results['deleted'], 5)

        # Verify soft delete
        for txn in self.transactions:
            txn.refresh_from_db()
            self.assertTrue(txn.metadata.get('deleted'))

    def test_batch_approve(self):
        """Test batch approval."""
        results = self.service.batch_approve(
            self.transaction_ids,
            self.user
        )

        self.assertEqual(results['approved'], 5)

        # Verify approval
        for txn in self.transactions:
            txn.refresh_from_db()
            self.assertTrue(txn.metadata.get('approved'))
            self.assertIsNotNone(txn.metadata.get('approved_at'))

    def test_batch_recalculate_amounts(self):
        """Test batch amount recalculation."""
        # Set up transactions with tax
        for txn in self.transactions:
            txn.tax_amount = Decimal('5.00')
            txn.save()

        results = self.service.batch_recalculate_amounts(
            self.transaction_ids
        )

        self.assertEqual(results['recalculated'], 5)

        # Verify calculations
        for txn in self.transactions:
            txn.refresh_from_db()
            expected_net = txn.gross_amount - txn.tax_amount
            self.assertEqual(txn.net_amount, expected_net)

    def test_preview_batch_operation(self):
        """Test preview functionality."""
        preview = self.service.preview_batch_operation(
            operation='categorize',
            transaction_ids=self.transaction_ids[:3],
            parameters={'account_id': str(self.test_account.id)}
        )

        self.assertEqual(preview['total_transactions'], 3)
        self.assertIn('affected_transactions', preview)
        self.assertEqual(len(preview['affected_transactions']), 3)

    def test_batch_operation_error_handling(self):
        """Test error handling in batch operations."""
        # Include invalid transaction ID
        invalid_ids = self.transaction_ids + ['invalid-uuid']

        results = self.service.batch_update_fields(
            invalid_ids,
            {'category': 'Test'}
        )

        # Should process valid IDs successfully
        self.assertEqual(results['updated'], 5)

    def test_batch_operation_partial_failure(self):
        """Test partial failures in batch operations."""
        # Use invalid account ID
        results = self.service.batch_categorize(
            self.transaction_ids,
            'invalid-account-id'
        )

        # Should fail for all transactions
        self.assertEqual(results['failed'], len(self.transaction_ids))
        self.assertGreater(len(results['errors']), 0)
