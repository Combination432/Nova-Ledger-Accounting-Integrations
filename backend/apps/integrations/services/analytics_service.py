"""
Advanced analytics and dashboard service.
Provides business intelligence and KPIs.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from apps.transactions.models import Transaction
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for advanced analytics and dashboard KPIs.
    """

    def __init__(self, organization):
        """
        Initialize analytics service.

        Args:
            organization: Organization object
        """
        self.organization = organization

    def get_dashboard_kpis(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Get key performance indicators for dashboard.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with KPIs
        """
        # Get previous period for comparison
        period_length = (end_date - start_date).days
        prev_start = start_date - timedelta(days=period_length)
        prev_end = start_date - timedelta(days=1)

        # Current period
        current_revenue = self._get_revenue(start_date, end_date)
        current_expenses = self._get_expenses(start_date, end_date)
        current_transactions = self._get_transaction_count(start_date, end_date)

        # Previous period
        prev_revenue = self._get_revenue(prev_start, prev_end)
        prev_expenses = self._get_expenses(prev_start, prev_end)
        prev_transactions = self._get_transaction_count(prev_start, prev_end)

        # Calculate changes
        revenue_change = self._calculate_change(current_revenue, prev_revenue)
        expense_change = self._calculate_change(current_expenses, prev_expenses)
        profit = current_revenue - current_expenses
        prev_profit = prev_revenue - prev_expenses
        profit_change = self._calculate_change(profit, prev_profit)

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'revenue': {
                'current': float(current_revenue),
                'previous': float(prev_revenue),
                'change_percent': revenue_change,
                'trend': 'up' if revenue_change > 0 else 'down' if revenue_change < 0 else 'flat'
            },
            'expenses': {
                'current': float(current_expenses),
                'previous': float(prev_expenses),
                'change_percent': expense_change,
                'trend': 'up' if expense_change > 0 else 'down' if expense_change < 0 else 'flat'
            },
            'profit': {
                'current': float(profit),
                'previous': float(prev_profit),
                'change_percent': profit_change,
                'margin_percent': (float(profit) / float(current_revenue) * 100) if current_revenue > 0 else 0
            },
            'transactions': {
                'current': current_transactions,
                'previous': prev_transactions,
                'change_percent': self._calculate_change(
                    Decimal(str(current_transactions)),
                    Decimal(str(prev_transactions))
                )
            }
        }

    def get_revenue_trend(
        self,
        start_date: date,
        end_date: date,
        interval: str = 'day'
    ) -> Dict:
        """
        Get revenue trend over time.

        Args:
            start_date: Start date
            end_date: End date
            interval: 'day', 'week', or 'month'

        Returns:
            Dict with revenue trend data
        """
        sales = Transaction.objects.filter(
            organization=self.organization,
            transaction_type='sale',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        if interval == 'day':
            trend = sales.values('transaction_date').annotate(
                revenue=Sum('gross_amount')
            ).order_by('transaction_date')
        elif interval == 'week':
            trend = sales.extra(
                select={'week': 'EXTRACT(week FROM transaction_date)'}
            ).values('week').annotate(
                revenue=Sum('gross_amount')
            ).order_by('week')
        elif interval == 'month':
            trend = sales.extra(
                select={'month': 'EXTRACT(month FROM transaction_date)'}
            ).values('month').annotate(
                revenue=Sum('gross_amount')
            ).order_by('month')

        return {
            'interval': interval,
            'data': [
                {
                    **{k: v.isoformat() if isinstance(v, date) else v for k, v in point.items() if k != 'revenue'},
                    'revenue': float(point['revenue'] or 0)
                }
                for point in trend
            ]
        }

    def get_category_breakdown(
        self,
        start_date: date,
        end_date: date,
        transaction_type: str = 'all'
    ) -> Dict:
        """
        Get breakdown by category.

        Args:
            start_date: Start date
            end_date: End date
            transaction_type: 'sale', 'expense', or 'all'

        Returns:
            Dict with category breakdown
        """
        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        if transaction_type != 'all':
            transactions = transactions.filter(transaction_type=transaction_type)

        breakdown = transactions.values('category').annotate(
            total_amount=Sum('gross_amount'),
            count=Count('id')
        ).order_by('-total_amount')

        total = sum(item['total_amount'] or 0 for item in breakdown)

        return {
            'total_amount': float(total),
            'categories': [
                {
                    'category': item['category'] or 'Uncategorized',
                    'amount': float(item['total_amount'] or 0),
                    'count': item['count'],
                    'percentage': (float(item['total_amount'] or 0) / float(total) * 100) if total > 0 else 0
                }
                for item in breakdown
            ]
        }

    def get_platform_performance(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Get performance metrics by platform.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with platform performance
        """
        platforms = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).values('source_platform').annotate(
            total_revenue=Sum('gross_amount', filter=Q(transaction_type='sale')),
            total_transactions=Count('id'),
            avg_transaction_value=Avg('gross_amount', filter=Q(transaction_type='sale'))
        ).order_by('-total_revenue')

        return {
            'platforms': [
                {
                    'platform': item['source_platform'] or 'Unknown',
                    'revenue': float(item['total_revenue'] or 0),
                    'transactions': item['total_transactions'],
                    'avg_transaction_value': float(item['avg_transaction_value'] or 0)
                }
                for item in platforms
            ]
        }

    def get_customer_analytics(
        self,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> Dict:
        """
        Get top customers by revenue.

        Args:
            start_date: Start date
            end_date: End date
            limit: Number of top customers to return

        Returns:
            Dict with customer analytics
        """
        customers = Transaction.objects.filter(
            organization=self.organization,
            transaction_type='sale',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            customer_name__isnull=False
        ).exclude(customer_name='').values('customer_name').annotate(
            total_revenue=Sum('gross_amount'),
            transaction_count=Count('id'),
            avg_order_value=Avg('gross_amount')
        ).order_by('-total_revenue')[:limit]

        return {
            'top_customers': [
                {
                    'customer_name': item['customer_name'],
                    'total_revenue': float(item['total_revenue'] or 0),
                    'orders': item['transaction_count'],
                    'avg_order_value': float(item['avg_order_value'] or 0)
                }
                for item in customers
            ]
        }

    def get_cash_flow_analysis(
        self,
        start_date: date,
        end_date: date,
        interval: str = 'month'
    ) -> Dict:
        """
        Analyze cash flow over time.

        Args:
            start_date: Start date
            end_date: End date
            interval: 'day', 'week', or 'month'

        Returns:
            Dict with cash flow analysis
        """
        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        )

        # Get inflows (sales, refunds received)
        inflows = transactions.filter(
            transaction_type__in=['sale']
        )

        # Get outflows (expenses, refunds issued)
        outflows = transactions.filter(
            transaction_type__in=['expense', 'refund']
        )

        if interval == 'month':
            inflow_data = inflows.extra(
                select={'period': 'EXTRACT(month FROM transaction_date)'}
            ).values('period').annotate(amount=Sum('gross_amount'))

            outflow_data = outflows.extra(
                select={'period': 'EXTRACT(month FROM transaction_date)'}
            ).values('period').annotate(amount=Sum('gross_amount'))

        # Combine data
        periods = {}
        for item in inflow_data:
            periods[item['period']] = {
                'inflow': float(item['amount'] or 0),
                'outflow': 0
            }

        for item in outflow_data:
            if item['period'] not in periods:
                periods[item['period']] = {'inflow': 0, 'outflow': 0}
            periods[item['period']]['outflow'] = float(item['amount'] or 0)

        # Calculate net flow
        flow_data = []
        for period, data in sorted(periods.items()):
            net_flow = data['inflow'] - data['outflow']
            flow_data.append({
                'period': int(period),
                'inflow': data['inflow'],
                'outflow': data['outflow'],
                'net_flow': net_flow
            })

        return {
            'interval': interval,
            'data': flow_data
        }

    def get_growth_metrics(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate growth metrics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dict with growth metrics
        """
        # Split period into months
        current_month_start = end_date.replace(day=1)
        prev_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

        # Current month metrics
        current_revenue = self._get_revenue(current_month_start, end_date)
        current_customers = self._get_unique_customers(current_month_start, end_date)

        # Previous month metrics
        prev_revenue = self._get_revenue(prev_month_start, current_month_start - timedelta(days=1))
        prev_customers = self._get_unique_customers(prev_month_start, current_month_start - timedelta(days=1))

        # Calculate growth rates
        revenue_growth = self._calculate_change(current_revenue, prev_revenue)
        customer_growth = self._calculate_change(
            Decimal(str(current_customers)),
            Decimal(str(prev_customers))
        )

        return {
            'period': {
                'current_month': current_month_start.isoformat(),
                'previous_month': prev_month_start.isoformat()
            },
            'revenue_growth_rate': revenue_growth,
            'customer_growth_rate': customer_growth,
            'metrics': {
                'current_revenue': float(current_revenue),
                'previous_revenue': float(prev_revenue),
                'current_customers': current_customers,
                'previous_customers': prev_customers
            }
        }

    def _get_revenue(self, start_date: date, end_date: date) -> Decimal:
        """Get total revenue for period."""
        result = Transaction.objects.filter(
            organization=self.organization,
            transaction_type='sale',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).aggregate(total=Sum('gross_amount'))

        return result['total'] or Decimal('0')

    def _get_expenses(self, start_date: date, end_date: date) -> Decimal:
        """Get total expenses for period."""
        result = Transaction.objects.filter(
            organization=self.organization,
            transaction_type='expense',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).aggregate(total=Sum('gross_amount'))

        return result['total'] or Decimal('0')

    def _get_transaction_count(self, start_date: date, end_date: date) -> int:
        """Get transaction count for period."""
        return Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date
        ).count()

    def _get_unique_customers(self, start_date: date, end_date: date) -> int:
        """Get unique customer count for period."""
        return Transaction.objects.filter(
            organization=self.organization,
            transaction_type='sale',
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            customer_name__isnull=False
        ).exclude(customer_name='').values('customer_name').distinct().count()

    def _calculate_change(self, current: Decimal, previous: Decimal) -> float:
        """Calculate percentage change."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0

        change = ((current - previous) / previous) * 100
        return float(change)
