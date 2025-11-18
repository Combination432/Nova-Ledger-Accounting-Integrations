"""
Reporting and profitability calculation services.
Generates channel P&Ls and product profitability - KEY DIFFERENTIATOR.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from .models import ChannelProfitability, ProductProfitability, DashboardMetric
from apps.transactions.models import Transaction, Fee
from apps.accounts.models import SalesChannel
from apps.inventory.models import InventoryItem
import logging

logger = logging.getLogger(__name__)


class ProfitabilityCalculator:
    """
    Calculate profitability metrics by channel, product, and customer.
    This is a KEY DIFFERENTIATOR - automatic, accurate channel P&Ls.
    """

    def __init__(self, organization):
        self.organization = organization

    def calculate_channel_profitability(
        self,
        sales_channel: SalesChannel,
        period_start: date,
        period_end: date,
        period_type: str = 'monthly'
    ) -> ChannelProfitability:
        """
        Calculate comprehensive P&L for a sales channel.

        Returns ChannelProfitability object with:
        - Gross sales
        - Returns/refunds
        - Net sales
        - Total COGS
        - Payment processing fees
        - Platform fees
        - Shipping costs
        - Gross profit & margin %
        - Net profit & margin %
        """
        # Get all transactions for this channel in period
        transactions = Transaction.objects.filter(
            organization=self.organization,
            sales_channel=sales_channel,
            transaction_date__gte=period_start,
            transaction_date__lte=period_end,
            transaction_type__in=['sale', 'refund']
        )

        # Calculate revenue components
        sales = transactions.filter(transaction_type='sale')
        refunds = transactions.filter(transaction_type='refund')

        gross_sales = sales.aggregate(Sum('gross_amount'))['gross_amount__sum'] or Decimal('0')
        returns_refunds = refunds.aggregate(Sum('gross_amount'))['gross_amount__sum'] or Decimal('0')
        net_sales = gross_sales - abs(returns_refunds)

        # Calculate COGS from line items
        total_cogs = Decimal('0')
        for txn in sales:
            for line_item in txn.line_items.all():
                if line_item.total_cogs:
                    total_cogs += line_item.total_cogs

        # Calculate fees by type
        payment_fees = Decimal('0')
        platform_fees = Decimal('0')
        shipping_costs = Decimal('0')
        other_fees = Decimal('0')

        for txn in transactions:
            for fee in txn.fees.all():
                if fee.fee_type in ['payment_processing', 'transaction_fee']:
                    payment_fees += fee.amount
                elif fee.fee_type in ['platform_fee', 'subscription_fee']:
                    platform_fees += fee.amount
                elif fee.fee_type == 'shipping_fee':
                    shipping_costs += fee.amount
                else:
                    other_fees += fee.amount

        # Calculate profitability metrics
        gross_profit = net_sales - total_cogs
        gross_margin_percent = (gross_profit / net_sales * 100) if net_sales > 0 else Decimal('0')

        total_fees = payment_fees + platform_fees + shipping_costs + other_fees
        net_profit = gross_profit - total_fees
        net_margin_percent = (net_profit / net_sales * 100) if net_sales > 0 else Decimal('0')

        # Additional metrics
        order_count = sales.count()
        units_sold = sum(
            line_item.quantity 
            for txn in sales 
            for line_item in txn.line_items.all()
        )
        avg_order_value = net_sales / order_count if order_count > 0 else Decimal('0')

        # Create or update profitability record
        profitability, created = ChannelProfitability.objects.update_or_create(
            organization=self.organization,
            sales_channel=sales_channel,
            period_start=period_start,
            period_type=period_type,
            defaults={
                'period_end': period_end,
                'gross_sales': gross_sales,
                'returns_refunds': abs(returns_refunds),
                'net_sales': net_sales,
                'total_cogs': total_cogs,
                'payment_processing_fees': payment_fees,
                'platform_fees': platform_fees,
                'shipping_costs': shipping_costs,
                'other_fees': other_fees,
                'gross_profit': gross_profit,
                'gross_margin_percent': gross_margin_percent,
                'net_profit': net_profit,
                'net_margin_percent': net_margin_percent,
                'order_count': order_count,
                'units_sold': int(units_sold),
                'average_order_value': avg_order_value
            }
        )

        logger.info(
            f"Channel Profitability for {sales_channel.name} "
            f"({period_start} to {period_end}): "
            f"Net Sales: ${net_sales}, Gross Profit: ${gross_profit} ({gross_margin_percent:.1f}%), "
            f"Net Profit: ${net_profit} ({net_margin_percent:.1f}%)"
        )

        return profitability

    def calculate_product_profitability(
        self,
        inventory_item: InventoryItem,
        period_start: date,
        period_end: date,
        sales_channel: SalesChannel = None
    ) -> ProductProfitability:
        """
        Calculate SKU-level profitability.

        Shows profitability for each product, optionally by channel.
        """
        from apps.transactions.models import TransactionLineItem

        # Get all line items for this product in period
        line_items_query = TransactionLineItem.objects.filter(
            inventory_item=inventory_item,
            transaction__organization=self.organization,
            transaction__transaction_date__gte=period_start,
            transaction__transaction_date__lte=period_end,
            transaction__transaction_type='sale'
        )

        if sales_channel:
            line_items_query = line_items_query.filter(
                transaction__sales_channel=sales_channel
            )

        line_items = line_items_query

        # Calculate metrics
        units_sold = line_items.aggregate(Sum('quantity'))['quantity__sum'] or Decimal('0')
        gross_revenue = line_items.aggregate(Sum('total_price'))['total_price__sum'] or Decimal('0')
        total_discounts = line_items.aggregate(Sum('discount_amount'))['discount_amount__sum'] or Decimal('0')
        net_revenue = gross_revenue - total_discounts

        total_cogs = line_items.aggregate(Sum('total_cogs'))['total_cogs__sum'] or Decimal('0')
        avg_cogs_per_unit = total_cogs / units_sold if units_sold > 0 else Decimal('0')

        # Allocate fees proportionally
        # For simplicity, using a flat 3% fee rate
        # In production, would aggregate actual fees from transactions
        allocated_fees = net_revenue * Decimal('0.03')

        gross_profit = net_revenue - total_cogs
        gross_margin_percent = (gross_profit / net_revenue * 100) if net_revenue > 0 else Decimal('0')

        # Create profitability record
        profitability, created = ProductProfitability.objects.update_or_create(
            organization=self.organization,
            inventory_item=inventory_item,
            period_start=period_start,
            sales_channel=sales_channel,
            defaults={
                'period_end': period_end,
                'period_type': 'monthly',
                'units_sold': units_sold,
                'gross_revenue': gross_revenue,
                'net_revenue': net_revenue,
                'total_cogs': total_cogs,
                'average_cogs_per_unit': avg_cogs_per_unit,
                'allocated_fees': allocated_fees,
                'gross_profit': gross_profit,
                'gross_margin_percent': gross_margin_percent
            }
        )

        logger.info(
            f"Product Profitability for {inventory_item.sku}: "
            f"Sold {units_sold} units, Revenue: ${net_revenue}, "
            f"Gross Margin: {gross_margin_percent:.1f}%"
        )

        return profitability

    def calculate_all_channel_profitability(
        self,
        period_start: date,
        period_end: date
    ) -> list:
        """Calculate profitability for all active sales channels."""
        channels = SalesChannel.objects.filter(
            organization=self.organization,
            is_active=True
        )

        results = []
        for channel in channels:
            prof = self.calculate_channel_profitability(
                channel, period_start, period_end
            )
            results.append(prof)

        return results

    def get_channel_rankings(self, period_start: date, period_end: date) -> list:
        """
        Get channels ranked by profitability.

        Returns list of channels sorted by net profit descending.
        """
        profitability_data = ChannelProfitability.objects.filter(
            organization=self.organization,
            period_start=period_start
        ).order_by('-net_profit')

        rankings = []
        for i, prof in enumerate(profitability_data, 1):
            rankings.append({
                'rank': i,
                'channel_name': prof.sales_channel.name,
                'net_sales': prof.net_sales,
                'gross_profit': prof.gross_profit,
                'net_profit': prof.net_profit,
                'net_margin_percent': prof.net_margin_percent,
                'order_count': prof.order_count
            })

        return rankings
