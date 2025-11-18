"""
Revenue Recognition services for Nova Ledger.
ASC 606 compliant revenue recognition and SaaS metrics calculation.
"""
from decimal import Decimal
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from .models import RevenueContract, RevenueSchedule, SubscriptionMetric, CustomerCohort
from apps.transactions.models import JournalEntry, JournalEntryLine
import logging

logger = logging.getLogger(__name__)


class RevenueRecognitionScheduler:
    """
    Generate revenue recognition schedules for contracts.
    Implements ASC 606 (GAAP) compliant revenue recognition.
    """

    @staticmethod
    @transaction.atomic
    def generate_schedule(
        contract: RevenueContract,
        recognition_method: str = 'straight_line',
        period_type: str = 'monthly'
    ) -> list:
        """
        Generate revenue recognition schedule for a contract.

        Args:
            contract: RevenueContract object
            recognition_method: 'straight_line', 'usage', 'milestone'
            period_type: 'daily', 'monthly', 'quarterly'

        Returns:
            List of RevenueSchedule objects
        """
        if contract.status != 'active':
            raise ValueError("Can only generate schedules for active contracts")

        # Clear existing schedules
        contract.schedules.all().delete()

        if recognition_method == 'straight_line':
            return RevenueRecognitionScheduler._generate_straight_line_schedule(
                contract, period_type
            )
        elif recognition_method == 'usage':
            raise NotImplementedError("Usage-based recognition not yet implemented")
        elif recognition_method == 'milestone':
            raise NotImplementedError("Milestone-based recognition not yet implemented")
        else:
            raise ValueError(f"Unknown recognition method: {recognition_method}")

    @staticmethod
    def _generate_straight_line_schedule(
        contract: RevenueContract,
        period_type: str = 'monthly'
    ) -> list:
        """
        Generate straight-line revenue recognition schedule.

        Revenue is recognized evenly over the contract period.
        """
        start_date = contract.start_date
        end_date = contract.end_date or (start_date + relativedelta(years=1))

        # Calculate number of periods
        if period_type == 'monthly':
            delta = relativedelta(months=1)
            num_periods = ((end_date.year - start_date.year) * 12 +
                          (end_date.month - start_date.month))
        elif period_type == 'quarterly':
            delta = relativedelta(months=3)
            num_periods = num_periods // 3
        elif period_type == 'daily':
            delta = timedelta(days=1)
            num_periods = (end_date - start_date).days
        else:
            raise ValueError(f"Unknown period type: {period_type}")

        if num_periods <= 0:
            num_periods = 1

        # Calculate amount per period
        amount_per_period = contract.total_contract_value / num_periods

        schedules = []
        current_date = start_date

        for i in range(num_periods):
            period_start = current_date
            period_end = current_date + delta - timedelta(days=1)

            # Ensure we don't go past contract end date
            if period_end > end_date:
                period_end = end_date

            recognition_date = period_end  # Recognize at end of period

            schedule = RevenueSchedule.objects.create(
                contract=contract,
                period_start_date=period_start,
                period_end_date=period_end,
                recognition_date=recognition_date,
                scheduled_amount=amount_per_period,
                is_recognized=False
            )

            schedules.append(schedule)
            current_date += delta

        # Update contract
        contract.deferred_revenue = contract.total_contract_value
        contract.recognized_revenue = Decimal('0')
        contract.save()

        logger.info(
            f"Generated {len(schedules)} recognition schedules for "
            f"contract {contract.contract_number} "
            f"(${amount_per_period} per {period_type})"
        )

        return schedules

    @staticmethod
    @transaction.atomic
    def recognize_revenue(schedule: RevenueSchedule) -> JournalEntry:
        """
        Create journal entry to recognize revenue for a schedule period.

        Journal Entry:
        DR Deferred Revenue (Liability)
            CR Revenue (Income)
        """
        if schedule.is_recognized:
            raise ValueError("Revenue already recognized for this schedule")

        contract = schedule.contract

        # Create journal entry
        entry = JournalEntry.objects.create(
            organization=contract.organization,
            entry_number=f"REV-{contract.contract_number}-{schedule.id}",
            entry_date=schedule.recognition_date,
            posting_date=schedule.recognition_date,
            description=f"Revenue recognition for {contract.customer_name} - Period ending {schedule.period_end_date}",
            status='posted'
        )

        # DR Deferred Revenue
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=contract.deferred_revenue_account,
            description="Deferred revenue recognition",
            debit_amount=schedule.scheduled_amount,
            credit_amount=Decimal('0')
        )

        # CR Revenue
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=contract.revenue_account,
            description=f"Revenue: {contract.customer_name}",
            debit_amount=Decimal('0'),
            credit_amount=schedule.scheduled_amount
        )

        # Mark schedule as recognized
        schedule.is_recognized = True
        schedule.recognized_amount = schedule.scheduled_amount
        schedule.recognized_at = timezone.now()
        schedule.journal_entry = entry
        schedule.save()

        # Update contract balances
        contract.recognized_revenue += schedule.scheduled_amount
        contract.deferred_revenue -= schedule.scheduled_amount
        contract.save()

        logger.info(
            f"Recognized ${schedule.scheduled_amount} revenue for "
            f"contract {contract.contract_number}. "
            f"Remaining deferred: ${contract.deferred_revenue}"
        )

        return entry


class SaaSMetricsCalculator:
    """
    Calculate SaaS metrics (MRR, ARR, Churn, LTV, CAC).
    This is a KEY DIFFERENTIATOR for Nova Ledger.
    """

    def __init__(self, organization):
        self.organization = organization

    @transaction.atomic
    def calculate_mrr(self, as_of_date: date = None) -> Dict:
        """
        Calculate Monthly Recurring Revenue (MRR).

        Components:
        - New MRR: From new customers
        - Expansion MRR: Upgrades from existing customers
        - Contraction MRR: Downgrades
        - Churned MRR: Cancelled subscriptions

        Returns:
            Dict with MRR breakdown
        """
        if not as_of_date:
            as_of_date = timezone.now().date()

        # Get active contracts as of date
        active_contracts = RevenueContract.objects.filter(
            organization=self.organization,
            start_date__lte=as_of_date,
            status='active'
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=as_of_date)
        )

        # Calculate total MRR from active contracts
        # Assuming contract values are annual, divide by 12 for monthly
        total_mrr = Decimal('0')
        for contract in active_contracts:
            # Simple calculation - would need more logic for actual implementation
            monthly_value = contract.total_contract_value / 12
            total_mrr += monthly_value

        # For new MRR, expansion, contraction - need historical comparison
        # This is simplified
        new_mrr = Decimal('0')  # Would calculate from contracts started this month
        expansion_mrr = Decimal('0')  # Would calculate from upgrades
        contraction_mrr = Decimal('0')  # Would calculate from downgrades
        churned_mrr = Decimal('0')  # Would calculate from cancellations

        # Store metric
        metric = SubscriptionMetric.objects.create(
            organization=self.organization,
            metric_type='mrr',
            metric_date=as_of_date,
            value=total_mrr,
            calculation_details={
                'new_mrr': float(new_mrr),
                'expansion_mrr': float(expansion_mrr),
                'contraction_mrr': float(contraction_mrr),
                'churned_mrr': float(churned_mrr),
                'total_mrr': float(total_mrr)
            }
        )

        logger.info(f"Calculated MRR for {as_of_date}: ${total_mrr}")

        return {
            'total_mrr': total_mrr,
            'new_mrr': new_mrr,
            'expansion_mrr': expansion_mrr,
            'contraction_mrr': contraction_mrr,
            'churned_mrr': churned_mrr
        }

    def calculate_arr(self, as_of_date: date = None) -> Decimal:
        """Calculate Annual Recurring Revenue (ARR)."""
        mrr_data = self.calculate_mrr(as_of_date)
        arr = mrr_data['total_mrr'] * 12

        SubscriptionMetric.objects.create(
            organization=self.organization,
            metric_type='arr',
            metric_date=as_of_date or timezone.now().date(),
            value=arr
        )

        return arr

    def calculate_ltv(
        self,
        average_revenue_per_customer: Decimal,
        gross_margin_percent: Decimal,
        monthly_churn_rate: Decimal
    ) -> Decimal:
        """
        Calculate Customer Lifetime Value (LTV).

        Formula:
        LTV = (Average Revenue per Customer * Gross Margin %) / Monthly Churn Rate
        """
        if monthly_churn_rate == 0:
            raise ValueError("Churn rate cannot be zero")

        ltv = (average_revenue_per_customer * (gross_margin_percent / 100)) / monthly_churn_rate

        logger.info(f"Calculated LTV: ${ltv}")

        return ltv

    def calculate_cac(
        self,
        total_sales_marketing_spend: Decimal,
        new_customers_acquired: int
    ) -> Decimal:
        """
        Calculate Customer Acquisition Cost (CAC).

        Formula:
        CAC = Total Sales & Marketing Spend / New Customers Acquired
        """
        if new_customers_acquired == 0:
            return Decimal('0')

        cac = total_sales_marketing_spend / new_customers_acquired

        logger.info(f"Calculated CAC: ${cac}")

        return cac
