"""
Batch operations service for bulk transaction management.
Handles bulk edit, categorize, tag, and delete operations.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import Q
from apps.transactions.models import Transaction
from apps.accounts.models import ChartOfAccounts
import logging

logger = logging.getLogger(__name__)


class BatchOperationsService:
    """
    Service for batch operations on transactions.
    """

    def __init__(self, organization):
        """
        Initialize batch operations service.

        Args:
            organization: Organization object
        """
        self.organization = organization

    def batch_categorize(
        self,
        transaction_ids: List[str],
        account_id: str
    ) -> Dict:
        """
        Categorize multiple transactions to an account.

        Args:
            transaction_ids: List of transaction IDs
            account_id: Chart of accounts ID

        Returns:
            Dict with operation results
        """
        results = {
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        try:
            account = ChartOfAccounts.objects.get(
                id=account_id,
                organization=self.organization
            )

            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        # Update category
                        txn.category = account.account_name
                        txn.metadata = txn.metadata or {}
                        txn.metadata['gl_account_id'] = str(account.id)
                        txn.metadata['gl_account_number'] = account.account_number
                        txn.save()

                        results['updated'] += 1

                    except Exception as e:
                        logger.error(f"Failed to categorize transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except ChartOfAccounts.DoesNotExist:
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': 'Account not found'})

        except Exception as e:
            logger.error(f"Batch categorize failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_tag(
        self,
        transaction_ids: List[str],
        tags: List[str],
        action: str = 'add'
    ) -> Dict:
        """
        Add or remove tags from multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            tags: List of tags
            action: 'add' or 'remove'

        Returns:
            Dict with operation results
        """
        results = {
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        try:
            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        txn.metadata = txn.metadata or {}
                        current_tags = set(txn.metadata.get('tags', []))

                        if action == 'add':
                            current_tags.update(tags)
                        elif action == 'remove':
                            current_tags.difference_update(tags)

                        txn.metadata['tags'] = list(current_tags)
                        txn.save()

                        results['updated'] += 1

                    except Exception as e:
                        logger.error(f"Failed to tag transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"Batch tag failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_update_fields(
        self,
        transaction_ids: List[str],
        field_updates: Dict
    ) -> Dict:
        """
        Update specific fields on multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            field_updates: Dict of field names and values to update

        Returns:
            Dict with operation results
        """
        results = {
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        # Allowed fields for batch update
        allowed_fields = [
            'category', 'description', 'customer_name',
            'currency', 'status'
        ]

        # Validate fields
        for field in field_updates.keys():
            if field not in allowed_fields:
                results['errors'].append({
                    'error': f"Field '{field}' not allowed for batch update"
                })
                return results

        try:
            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        # Update fields
                        for field, value in field_updates.items():
                            setattr(txn, field, value)

                        txn.save()
                        results['updated'] += 1

                    except Exception as e:
                        logger.error(f"Failed to update transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"Batch update failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_delete(
        self,
        transaction_ids: List[str],
        soft_delete: bool = True
    ) -> Dict:
        """
        Delete multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            soft_delete: If True, mark as deleted instead of removing from DB

        Returns:
            Dict with operation results
        """
        results = {
            'deleted': 0,
            'failed': 0,
            'errors': []
        }

        try:
            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        if soft_delete:
                            # Soft delete - mark as deleted
                            txn.metadata = txn.metadata or {}
                            txn.metadata['deleted'] = True
                            txn.metadata['deleted_at'] = timezone.now().isoformat()
                            txn.save()
                        else:
                            # Hard delete - remove from database
                            txn.delete()

                        results['deleted'] += 1

                    except Exception as e:
                        logger.error(f"Failed to delete transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"Batch delete failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_approve(
        self,
        transaction_ids: List[str],
        approved_by
    ) -> Dict:
        """
        Approve multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            approved_by: User approving the transactions

        Returns:
            Dict with operation results
        """
        results = {
            'approved': 0,
            'failed': 0,
            'errors': []
        }

        try:
            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        txn.metadata = txn.metadata or {}
                        txn.metadata['approved'] = True
                        txn.metadata['approved_by'] = approved_by.get_full_name()
                        txn.metadata['approved_at'] = timezone.now().isoformat()
                        txn.save()

                        results['approved'] += 1

                    except Exception as e:
                        logger.error(f"Failed to approve transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"Batch approve failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_apply_rule(
        self,
        transaction_ids: List[str],
        rule_id: str
    ) -> Dict:
        """
        Apply a categorization rule to multiple transactions.

        Args:
            transaction_ids: List of transaction IDs
            rule_id: TransactionRule ID to apply

        Returns:
            Dict with operation results
        """
        from .categorization_service import AutoCategorizationService
        from ..models import TransactionRule

        results = {
            'categorized': 0,
            'failed': 0,
            'errors': []
        }

        try:
            rule = TransactionRule.objects.get(
                id=rule_id,
                organization=self.organization
            )

            categorization_service = AutoCategorizationService(self.organization)

            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        # Apply rule to transaction
                        result = categorization_service._apply_rule(rule, txn)

                        if result:
                            results['categorized'] += 1
                        else:
                            results['failed'] += 1
                            results['errors'].append({
                                'transaction_id': str(txn.id),
                                'error': 'Rule did not match'
                            })

                    except Exception as e:
                        logger.error(f"Failed to apply rule to transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

                # Update rule statistics
                rule.times_applied += results['categorized']
                rule.last_applied_at = timezone.now()
                rule.save()

        except TransactionRule.DoesNotExist:
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': 'Rule not found'})

        except Exception as e:
            logger.error(f"Batch apply rule failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def batch_recalculate_amounts(
        self,
        transaction_ids: List[str]
    ) -> Dict:
        """
        Recalculate net amounts, taxes, and fees for transactions.

        Args:
            transaction_ids: List of transaction IDs

        Returns:
            Dict with operation results
        """
        results = {
            'recalculated': 0,
            'failed': 0,
            'errors': []
        }

        try:
            with db_transaction.atomic():
                transactions = Transaction.objects.filter(
                    id__in=transaction_ids,
                    organization=self.organization
                )

                for txn in transactions:
                    try:
                        # Recalculate net amount
                        tax = txn.tax_amount or Decimal('0')
                        txn.net_amount = txn.gross_amount - tax

                        # Recalculate currency conversion if needed
                        if txn.currency and txn.currency != 'USD':
                            from .currency_service import CurrencyService
                            currency_service = CurrencyService(self.organization)

                            # Convert to base currency
                            converted = currency_service.convert_amount(
                                txn.gross_amount,
                                txn.currency,
                                'USD',
                                txn.transaction_date
                            )

                            txn.metadata = txn.metadata or {}
                            txn.metadata['converted_amount'] = float(converted)
                            txn.metadata['conversion_rate'] = float(
                                currency_service.get_exchange_rate(
                                    txn.currency,
                                    'USD',
                                    txn.transaction_date
                                )
                            )

                        txn.save()
                        results['recalculated'] += 1

                    except Exception as e:
                        logger.error(f"Failed to recalculate transaction {txn.id}: {str(e)}")
                        results['failed'] += 1
                        results['errors'].append({
                            'transaction_id': str(txn.id),
                            'error': str(e)
                        })

        except Exception as e:
            logger.error(f"Batch recalculate failed: {str(e)}")
            results['failed'] = len(transaction_ids)
            results['errors'].append({'error': str(e)})

        return results

    def preview_batch_operation(
        self,
        operation: str,
        transaction_ids: List[str],
        parameters: Dict
    ) -> Dict:
        """
        Preview the results of a batch operation without executing it.

        Args:
            operation: Operation type (categorize, tag, update, delete)
            transaction_ids: List of transaction IDs
            parameters: Operation parameters

        Returns:
            Dict with preview results
        """
        try:
            transactions = Transaction.objects.filter(
                id__in=transaction_ids,
                organization=self.organization
            )

            preview = {
                'operation': operation,
                'total_transactions': transactions.count(),
                'parameters': parameters,
                'affected_transactions': [],
                'warnings': []
            }

            # Check for potential issues
            for txn in transactions[:10]:  # Preview first 10
                txn_preview = {
                    'id': str(txn.id),
                    'date': txn.transaction_date.isoformat(),
                    'description': txn.description,
                    'amount': float(txn.gross_amount),
                    'current_category': txn.category
                }

                # Add operation-specific preview
                if operation == 'categorize':
                    try:
                        account = ChartOfAccounts.objects.get(
                            id=parameters.get('account_id'),
                            organization=self.organization
                        )
                        txn_preview['new_category'] = account.account_name
                    except ChartOfAccounts.DoesNotExist:
                        preview['warnings'].append('Target account not found')

                elif operation == 'tag':
                    current_tags = txn.metadata.get('tags', []) if txn.metadata else []
                    txn_preview['current_tags'] = current_tags
                    txn_preview['new_tags'] = list(set(current_tags + parameters.get('tags', [])))

                preview['affected_transactions'].append(txn_preview)

            return preview

        except Exception as e:
            logger.error(f"Preview failed: {str(e)}")
            return {'error': str(e)}
