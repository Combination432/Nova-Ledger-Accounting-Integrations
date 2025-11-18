"""
Bank reconciliation matching service.
Implements fuzzy matching algorithm for automatic transaction matching.
"""
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from ..models import BankReconciliation, ReconciliationMatch
from apps.transactions.models import BankTransaction, Transaction
import logging

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Service for matching bank transactions to accounting transactions.
    Implements multi-level matching strategy similar to Synder.
    """

    def __init__(self, reconciliation: BankReconciliation):
        self.reconciliation = reconciliation
        self.organization = reconciliation.organization
        self.bank_account = reconciliation.bank_account

    def auto_match(self, confidence_threshold: float = 80.0) -> Dict:
        """
        Automatically match bank transactions to accounting transactions.

        Args:
            confidence_threshold: Minimum confidence score to auto-match (0-100)

        Returns:
            Dict with matching statistics
        """
        # Get unmatched bank transactions in period
        bank_transactions = BankTransaction.objects.filter(
            organization=self.organization,
            bank_account=self.bank_account,
            transaction_date__gte=self.reconciliation.period_start,
            transaction_date__lte=self.reconciliation.period_end
        ).exclude(
            id__in=ReconciliationMatch.objects.filter(
                reconciliation=self.reconciliation
            ).values_list('bank_transaction_id', flat=True)
        )

        exact_matches = 0
        fuzzy_matches = 0
        suggestions = 0
        unmatched = 0

        for bank_txn in bank_transactions:
            # Try exact match first
            exact_match = self._find_exact_match(bank_txn)
            if exact_match:
                self._create_match(
                    bank_txn,
                    [exact_match],
                    match_type='exact',
                    confidence=100.0,
                    auto_confirm=True
                )
                exact_matches += 1
                continue

            # Try fuzzy match
            fuzzy_results = self._find_fuzzy_matches(bank_txn, limit=5)
            if fuzzy_results:
                best_match = fuzzy_results[0]
                confidence = best_match['confidence']

                if confidence >= confidence_threshold:
                    self._create_match(
                        bank_txn,
                        [best_match['transaction']],
                        match_type='fuzzy',
                        confidence=confidence,
                        amount_variance=best_match['amount_variance'],
                        date_variance=best_match['date_variance'],
                        auto_confirm=(confidence >= 95.0)
                    )
                    fuzzy_matches += 1
                else:
                    # Create suggestion for manual review
                    self._create_match(
                        bank_txn,
                        [best_match['transaction']],
                        match_type='suggested',
                        confidence=confidence,
                        amount_variance=best_match['amount_variance'],
                        date_variance=best_match['date_variance'],
                        auto_confirm=False
                    )
                    suggestions += 1
            else:
                unmatched += 1

        # Update reconciliation summary
        self.reconciliation.total_matched = exact_matches + fuzzy_matches
        self.reconciliation.total_suggested = suggestions
        self.reconciliation.total_unmatched = unmatched
        self.reconciliation.save()

        return {
            'exact_matches': exact_matches,
            'fuzzy_matches': fuzzy_matches,
            'suggestions': suggestions,
            'unmatched': unmatched,
            'total_processed': len(bank_transactions)
        }

    def _find_exact_match(self, bank_txn: BankTransaction) -> Optional[Transaction]:
        """
        Find exact match for a bank transaction.

        Exact match criteria:
        - Same amount (to the penny)
        - Same date
        - Not already matched
        """
        # Look for transactions on the same date with same amount
        candidates = Transaction.objects.filter(
            organization=self.organization,
            transaction_date=bank_txn.transaction_date,
            gross_amount=bank_txn.amount
        ).exclude(
            id__in=ReconciliationMatch.objects.filter(
                reconciliation__organization=self.organization
            ).values_list('transactions__id', flat=True)
        )

        if candidates.count() == 1:
            return candidates.first()

        return None

    def _find_fuzzy_matches(
        self,
        bank_txn: BankTransaction,
        limit: int = 5
    ) -> List[Dict]:
        """
        Find fuzzy matches for a bank transaction.

        Fuzzy matching allows:
        - Amount variance up to $0.01
        - Date variance up to 2 days
        - Description similarity

        Args:
            bank_txn: Bank transaction to match
            limit: Maximum number of matches to return

        Returns:
            List of match candidates with confidence scores
        """
        # Search window: ±2 days
        date_min = bank_txn.transaction_date - timedelta(days=2)
        date_max = bank_txn.transaction_date + timedelta(days=2)

        # Amount window: ±$0.01
        amount_min = bank_txn.amount - Decimal('0.01')
        amount_max = bank_txn.amount + Decimal('0.01')

        # Find candidates
        candidates = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=date_min,
            transaction_date__lte=date_max,
            gross_amount__gte=amount_min,
            gross_amount__lte=amount_max
        ).exclude(
            id__in=ReconciliationMatch.objects.filter(
                reconciliation__organization=self.organization
            ).values_list('transactions__id', flat=True)
        )[:20]  # Limit candidates for performance

        # Score each candidate
        matches = []
        for candidate in candidates:
            score = self._calculate_match_score(bank_txn, candidate)
            if score > 50:  # Minimum threshold for consideration
                matches.append({
                    'transaction': candidate,
                    'confidence': score,
                    'amount_variance': abs(bank_txn.amount - candidate.gross_amount),
                    'date_variance': abs((bank_txn.transaction_date - candidate.transaction_date).days)
                })

        # Sort by confidence and return top matches
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        return matches[:limit]

    def _calculate_match_score(
        self,
        bank_txn: BankTransaction,
        transaction: Transaction
    ) -> float:
        """
        Calculate confidence score for a potential match (0-100).

        Scoring factors:
        - Amount difference: 0 = +40 points, $0.01 = +20 points
        - Date difference: 0 days = +40 points, 1 day = +20 points, 2 days = +10 points
        - Description similarity: up to +20 points

        Args:
            bank_txn: Bank transaction
            transaction: Candidate accounting transaction

        Returns:
            Confidence score (0-100)
        """
        score = 0.0

        # Amount scoring
        amount_diff = abs(bank_txn.amount - transaction.gross_amount)
        if amount_diff == 0:
            score += 40
        elif amount_diff <= Decimal('0.01'):
            score += 20

        # Date scoring
        date_diff = abs((bank_txn.transaction_date - transaction.transaction_date).days)
        if date_diff == 0:
            score += 40
        elif date_diff == 1:
            score += 20
        elif date_diff == 2:
            score += 10

        # Description similarity
        bank_desc = (bank_txn.description or '').lower()
        txn_desc = (transaction.description or '').lower()

        if bank_desc and txn_desc:
            similarity = self._calculate_text_similarity(bank_desc, txn_desc)
            score += similarity * 20  # Max 20 points

        return min(score, 100.0)

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity (0-1).
        Uses basic word overlap for simplicity.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _create_match(
        self,
        bank_txn: BankTransaction,
        transactions: List[Transaction],
        match_type: str,
        confidence: float,
        amount_variance: Decimal = Decimal('0'),
        date_variance: int = 0,
        auto_confirm: bool = False
    ) -> ReconciliationMatch:
        """
        Create a reconciliation match.

        Args:
            bank_txn: Bank transaction
            transactions: List of matching accounting transactions
            match_type: Type of match (exact, fuzzy, manual, suggested)
            confidence: Confidence score (0-100)
            amount_variance: Amount difference
            date_variance: Date difference in days
            auto_confirm: Whether to auto-confirm the match

        Returns:
            Created ReconciliationMatch
        """
        match = ReconciliationMatch.objects.create(
            reconciliation=self.reconciliation,
            bank_transaction=bank_txn,
            match_type=match_type,
            confidence_score=confidence,
            amount_variance=amount_variance,
            date_variance_days=date_variance,
            is_confirmed=auto_confirm
        )

        # Add transaction relationships
        match.transactions.set(transactions)

        if auto_confirm:
            match.confirmed_at = timezone.now()
            match.save()

        logger.info(
            f"Created {match_type} match for bank transaction {bank_txn.id} "
            f"(confidence: {confidence}%, confirmed: {auto_confirm})"
        )

        return match

    def manual_match(
        self,
        bank_transaction_id: str,
        transaction_ids: List[str],
        notes: str = ''
    ) -> ReconciliationMatch:
        """
        Create a manual match between bank transaction and accounting transaction(s).

        Args:
            bank_transaction_id: Bank transaction ID
            transaction_ids: List of accounting transaction IDs to match
            notes: Optional notes about the match

        Returns:
            Created ReconciliationMatch
        """
        bank_txn = BankTransaction.objects.get(id=bank_transaction_id)
        transactions = Transaction.objects.filter(id__in=transaction_ids)

        match = ReconciliationMatch.objects.create(
            reconciliation=self.reconciliation,
            bank_transaction=bank_txn,
            match_type='manual',
            confidence_score=100.0,
            is_confirmed=True,
            confirmed_at=timezone.now(),
            notes=notes
        )

        match.transactions.set(transactions)

        logger.info(f"Created manual match for bank transaction {bank_transaction_id}")

        return match

    def unmatch(self, match_id: str) -> bool:
        """
        Remove a reconciliation match.

        Args:
            match_id: ReconciliationMatch ID

        Returns:
            True if successful
        """
        try:
            match = ReconciliationMatch.objects.get(
                id=match_id,
                reconciliation=self.reconciliation
            )
            match.delete()

            logger.info(f"Removed reconciliation match {match_id}")
            return True

        except ReconciliationMatch.DoesNotExist:
            logger.error(f"Reconciliation match {match_id} not found")
            return False

    def complete_reconciliation(self, user) -> bool:
        """
        Mark reconciliation as completed.

        Args:
            user: User completing the reconciliation

        Returns:
            True if successful
        """
        # Check if all transactions are matched or reviewed
        unreviewed_matches = ReconciliationMatch.objects.filter(
            reconciliation=self.reconciliation,
            is_confirmed=False,
            match_type='suggested'
        ).count()

        if unreviewed_matches > 0:
            self.reconciliation.status = 'needs_review'
        else:
            self.reconciliation.status = 'completed'
            self.reconciliation.reconciled_by = user
            self.reconciliation.reconciled_at = timezone.now()

        self.reconciliation.save()

        logger.info(
            f"Reconciliation {self.reconciliation.id} marked as {self.reconciliation.status}"
        )

        return True

    def get_unmatched_transactions(self) -> Dict:
        """
        Get unmatched bank and accounting transactions for the reconciliation period.

        Returns:
            Dict with unmatched_bank and unmatched_accounting lists
        """
        # Unmatched bank transactions
        matched_bank_ids = ReconciliationMatch.objects.filter(
            reconciliation=self.reconciliation
        ).values_list('bank_transaction_id', flat=True)

        unmatched_bank = BankTransaction.objects.filter(
            organization=self.organization,
            bank_account=self.bank_account,
            transaction_date__gte=self.reconciliation.period_start,
            transaction_date__lte=self.reconciliation.period_end
        ).exclude(id__in=matched_bank_ids)

        # Unmatched accounting transactions
        matched_txn_ids = ReconciliationMatch.objects.filter(
            reconciliation__organization=self.organization
        ).values_list('transactions__id', flat=True)

        unmatched_accounting = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=self.reconciliation.period_start,
            transaction_date__lte=self.reconciliation.period_end,
            source_platform__isnull=False  # Only synced transactions
        ).exclude(id__in=matched_txn_ids)

        return {
            'unmatched_bank': list(unmatched_bank.values(
                'id', 'transaction_date', 'description', 'amount'
            )),
            'unmatched_accounting': list(unmatched_accounting.values(
                'id', 'transaction_date', 'description', 'gross_amount', 'source_platform'
            )),
            'unmatched_bank_count': unmatched_bank.count(),
            'unmatched_accounting_count': unmatched_accounting.count()
        }
