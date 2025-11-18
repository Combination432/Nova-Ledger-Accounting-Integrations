"""
Auto-categorization service for smart transaction classification.
Implements Synder-style rule matching for automatic GL account assignment.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from ..models import TransactionRule
from apps.transactions.models import Transaction
import logging
import re

logger = logging.getLogger(__name__)


class AutoCategorizationService:
    """
    Service for automatically categorizing transactions using rules.
    """

    def __init__(self, organization):
        self.organization = organization

    def categorize_transaction(self, transaction: Transaction) -> Optional[Dict]:
        """
        Apply categorization rules to a single transaction.

        Args:
            transaction: Transaction to categorize

        Returns:
            Dict with rule applied and actions taken, or None if no rule matched
        """
        # Get active rules ordered by priority
        rules = TransactionRule.objects.filter(
            organization=self.organization,
            is_active=True,
            auto_apply=True
        ).order_by('priority')

        # Filter by integration if transaction has source_platform
        if transaction.source_platform:
            rules = rules.filter(
                Q(integration__integration_type=transaction.source_platform) |
                Q(integration__isnull=True)
            )

        for rule in rules:
            if self._rule_matches(rule, transaction):
                logger.info(f"Rule '{rule.name}' matched transaction {transaction.id}")
                result = self._apply_rule(rule, transaction)

                # Update rule statistics
                rule.times_applied += 1
                rule.last_applied_at = timezone.now()
                rule.save(update_fields=['times_applied', 'last_applied_at'])

                return result

        logger.debug(f"No rules matched transaction {transaction.id}")
        return None

    def categorize_batch(self, transactions: List[Transaction]) -> Dict:
        """
        Categorize multiple transactions in batch.

        Args:
            transactions: List of transactions to categorize

        Returns:
            Dict with statistics: {categorized: int, skipped: int, rules_applied: {}}
        """
        categorized = 0
        skipped = 0
        rules_applied = {}

        for transaction in transactions:
            result = self.categorize_transaction(transaction)
            if result:
                categorized += 1
                rule_name = result['rule_name']
                rules_applied[rule_name] = rules_applied.get(rule_name, 0) + 1
            else:
                skipped += 1

        return {
            'categorized': categorized,
            'skipped': skipped,
            'total': len(transactions),
            'rules_applied': rules_applied
        }

    def _rule_matches(self, rule: TransactionRule, transaction: Transaction) -> bool:
        """
        Check if a rule matches a transaction.

        Args:
            rule: The rule to check
            transaction: The transaction to match against

        Returns:
            True if rule matches, False otherwise
        """
        rule_type = rule.rule_type
        conditions = rule.conditions

        if rule_type == 'contains':
            search_field = conditions.get('field', 'description')
            search_value = conditions.get('value', '').lower()
            transaction_value = str(getattr(transaction, search_field, '')).lower()
            return search_value in transaction_value

        elif rule_type == 'starts_with':
            search_field = conditions.get('field', 'description')
            search_value = conditions.get('value', '').lower()
            transaction_value = str(getattr(transaction, search_field, '')).lower()
            return transaction_value.startswith(search_value)

        elif rule_type == 'ends_with':
            search_field = conditions.get('field', 'description')
            search_value = conditions.get('value', '').lower()
            transaction_value = str(getattr(transaction, search_field, '')).lower()
            return transaction_value.endswith(search_value)

        elif rule_type == 'exact_match':
            search_field = conditions.get('field', 'description')
            search_value = conditions.get('value', '').lower()
            transaction_value = str(getattr(transaction, search_field, '')).lower()
            return transaction_value == search_value

        elif rule_type == 'amount_range':
            min_amount = Decimal(str(conditions.get('min_amount', 0)))
            max_amount = Decimal(str(conditions.get('max_amount', 999999999)))
            return min_amount <= transaction.gross_amount <= max_amount

        elif rule_type == 'customer_match':
            customer_pattern = conditions.get('customer_pattern', '').lower()
            customer_name = (transaction.customer_name or '').lower()
            customer_email = (transaction.customer_email or '').lower()
            return customer_pattern in customer_name or customer_pattern in customer_email

        elif rule_type == 'platform_match':
            platform = conditions.get('platform')
            return transaction.source_platform == platform

        elif rule_type == 'combined':
            # Combined conditions with AND/OR logic
            logic = conditions.get('logic', 'AND')  # AND or OR
            sub_conditions = conditions.get('conditions', [])

            results = []
            for sub_condition in sub_conditions:
                # Create a temporary rule for each sub-condition
                temp_rule = TransactionRule(
                    rule_type=sub_condition.get('rule_type'),
                    conditions=sub_condition.get('conditions', {})
                )
                results.append(self._rule_matches(temp_rule, transaction))

            if logic == 'AND':
                return all(results)
            else:  # OR
                return any(results)

        return False

    def _apply_rule(self, rule: TransactionRule, transaction: Transaction) -> Dict:
        """
        Apply a rule's actions to a transaction.

        Args:
            rule: The rule to apply
            transaction: The transaction to modify

        Returns:
            Dict with actions taken
        """
        actions_taken = []
        action = rule.action

        if action == 'categorize' and rule.target_account:
            # Note: This would need to create journal entries in a real implementation
            # For now, we just store the suggested account in metadata
            if not transaction.metadata:
                transaction.metadata = {}

            transaction.metadata['suggested_account_id'] = str(rule.target_account.id)
            transaction.metadata['suggested_account_name'] = rule.target_account.account_name
            transaction.metadata['categorization_rule_id'] = str(rule.id)
            transaction.metadata['categorization_rule_name'] = rule.name
            transaction.save(update_fields=['metadata'])

            actions_taken.append({
                'action': 'categorized',
                'account_id': str(rule.target_account.id),
                'account_name': rule.target_account.account_name
            })

        elif action == 'tag':
            # Add tags to transaction
            if not transaction.metadata:
                transaction.metadata = {}

            existing_tags = transaction.metadata.get('tags', [])
            new_tags = rule.tags
            combined_tags = list(set(existing_tags + new_tags))
            transaction.metadata['tags'] = combined_tags
            transaction.save(update_fields=['metadata'])

            actions_taken.append({
                'action': 'tagged',
                'tags': new_tags
            })

        elif action == 'split':
            # Mark for split transaction (requires manual review)
            if not transaction.metadata:
                transaction.metadata = {}

            transaction.metadata['requires_split'] = True
            transaction.metadata['split_config'] = rule.split_config
            transaction.metadata['split_rule_id'] = str(rule.id)
            transaction.save(update_fields=['metadata'])

            actions_taken.append({
                'action': 'marked_for_split',
                'config': rule.split_config
            })

        elif action == 'exclude':
            # Exclude from sync/reporting
            if not transaction.metadata:
                transaction.metadata = {}

            transaction.metadata['excluded'] = True
            transaction.metadata['exclusion_rule_id'] = str(rule.id)
            transaction.save(update_fields=['metadata'])

            actions_taken.append({
                'action': 'excluded'
            })

        return {
            'rule_id': str(rule.id),
            'rule_name': rule.name,
            'actions': actions_taken,
            'transaction_id': str(transaction.id)
        }

    def suggest_rules(self, transaction: Transaction, limit: int = 5) -> List[Dict]:
        """
        Suggest rules that might match a transaction without applying them.
        Useful for UI/manual review.

        Args:
            transaction: Transaction to analyze
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested rules with match scores
        """
        suggestions = []

        # Get all active rules
        rules = TransactionRule.objects.filter(
            organization=self.organization,
            is_active=True
        ).order_by('priority')[:limit * 2]  # Get more than needed for filtering

        for rule in rules:
            if self._rule_matches(rule, transaction):
                match_score = self._calculate_match_score(rule, transaction)
                suggestions.append({
                    'rule_id': str(rule.id),
                    'rule_name': rule.name,
                    'rule_type': rule.rule_type,
                    'action': rule.action,
                    'target_account': {
                        'id': str(rule.target_account.id),
                        'name': rule.target_account.account_name
                    } if rule.target_account else None,
                    'match_score': match_score,
                    'times_applied': rule.times_applied
                })

        # Sort by match score and limit
        suggestions.sort(key=lambda x: x['match_score'], reverse=True)
        return suggestions[:limit]

    def _calculate_match_score(self, rule: TransactionRule, transaction: Transaction) -> float:
        """
        Calculate how well a rule matches a transaction (0-100 score).

        Args:
            rule: The rule to score
            transaction: The transaction

        Returns:
            Match score (0-100)
        """
        score = 50.0  # Base score

        # Exact matches get higher scores
        if rule.rule_type == 'exact_match':
            score += 30

        # Higher priority rules get higher scores
        if rule.priority < 50:
            score += 10

        # Rules that have been applied successfully before get higher scores
        if rule.times_applied > 0:
            score += min(rule.times_applied / 10, 10)  # Max +10 points

        return min(score, 100.0)

    def learn_from_manual_categorization(
        self,
        transaction: Transaction,
        account_id: str,
        create_rule: bool = False
    ) -> Optional[TransactionRule]:
        """
        Learn from manual categorization to suggest or create new rules.

        Args:
            transaction: The transaction that was manually categorized
            account_id: The account it was categorized to
            create_rule: Whether to automatically create a rule

        Returns:
            Created rule if create_rule=True, None otherwise
        """
        # Analyze transaction to determine best rule type
        description = transaction.description or ''

        # Look for patterns in description
        if len(description) > 20:
            # Extract potential keywords
            keywords = self._extract_keywords(description)

            if keywords and create_rule:
                from apps.accounts.models import ChartOfAccounts

                account = ChartOfAccounts.objects.get(id=account_id)

                # Create a rule based on the first keyword
                rule = TransactionRule.objects.create(
                    organization=self.organization,
                    name=f"Auto: {keywords[0]} → {account.account_name}",
                    description=f"Auto-generated from manual categorization",
                    rule_type='contains',
                    action='categorize',
                    conditions={
                        'field': 'description',
                        'value': keywords[0]
                    },
                    target_account=account,
                    priority=200,  # Lower priority for auto-generated rules
                    auto_apply=False  # Require manual approval
                )

                logger.info(f"Created auto-generated rule: {rule.name}")
                return rule

        return None

    def _extract_keywords(self, text: str, min_length: int = 4) -> List[str]:
        """
        Extract potential keywords from text for rule generation.

        Args:
            text: Text to analyze
            min_length: Minimum keyword length

        Returns:
            List of keywords
        """
        # Remove common words
        stop_words = {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'order', 'payment'}

        # Split and clean
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter keywords
        keywords = [
            word for word in words
            if len(word) >= min_length and word not in stop_words
        ]

        # Return first 3 keywords
        return keywords[:3]
