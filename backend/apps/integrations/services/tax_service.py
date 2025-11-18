"""
Advanced tax reporting service.
Handles sales tax, VAT, 1099 reporting, and multi-jurisdiction tax tracking.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime
from django.db.models import Sum, Q, Count
from django.utils import timezone
from apps.transactions.models import Transaction
from ..models import TaxConfiguration
import logging

logger = logging.getLogger(__name__)


class TaxService:
    """
    Service for advanced tax reporting and compliance.
    """

    def __init__(self, organization):
        """
        Initialize tax service.

        Args:
            organization: Organization object
        """
        self.organization = organization

    def calculate_sales_tax_summary(
        self,
        start_date: date,
        end_date: date,
        jurisdiction: Optional[str] = None
    ) -> Dict:
        """
        Calculate sales tax summary by jurisdiction.

        Args:
            start_date: Start date for reporting period
            end_date: End date for reporting period
            jurisdiction: Optional filter for specific jurisdiction

        Returns:
            Dict with sales tax breakdown by jurisdiction
        """
        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='sale'
        )

        if jurisdiction:
            transactions = transactions.filter(
                metadata__tax_jurisdiction=jurisdiction
            )

        # Group by jurisdiction
        jurisdictions = {}

        for txn in transactions:
            tax_jurisdiction = txn.metadata.get('tax_jurisdiction', 'Unknown')
            tax_rate = Decimal(str(txn.metadata.get('tax_rate', 0)))

            if tax_jurisdiction not in jurisdictions:
                jurisdictions[tax_jurisdiction] = {
                    'jurisdiction': tax_jurisdiction,
                    'total_sales': Decimal('0'),
                    'taxable_sales': Decimal('0'),
                    'exempt_sales': Decimal('0'),
                    'tax_collected': Decimal('0'),
                    'tax_rate': tax_rate,
                    'transaction_count': 0
                }

            jur_data = jurisdictions[tax_jurisdiction]
            jur_data['total_sales'] += txn.gross_amount
            jur_data['transaction_count'] += 1

            # Check if transaction is taxable
            is_taxable = txn.metadata.get('is_taxable', True)

            if is_taxable:
                jur_data['taxable_sales'] += txn.net_amount
                jur_data['tax_collected'] += txn.tax_amount or Decimal('0')
            else:
                jur_data['exempt_sales'] += txn.gross_amount

        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'jurisdictions': list(jurisdictions.values()),
            'total_tax_collected': sum(j['tax_collected'] for j in jurisdictions.values()),
            'total_taxable_sales': sum(j['taxable_sales'] for j in jurisdictions.values()),
            'total_sales': sum(j['total_sales'] for j in jurisdictions.values())
        }

    def calculate_vat_summary(
        self,
        start_date: date,
        end_date: date,
        vat_scheme: str = 'standard'
    ) -> Dict:
        """
        Calculate VAT (Value Added Tax) summary.

        Args:
            start_date: Start date for reporting period
            end_date: End date for reporting period
            vat_scheme: VAT scheme (standard, flat_rate, cash_accounting)

        Returns:
            Dict with VAT summary including input/output VAT
        """
        # Output VAT (on sales)
        sales = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='sale'
        )

        # Input VAT (on purchases)
        purchases = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='expense'
        )

        # Calculate output VAT (VAT charged to customers)
        output_vat = Decimal('0')
        total_sales = Decimal('0')
        sales_by_rate = {}

        for sale in sales:
            vat_rate = Decimal(str(sale.metadata.get('vat_rate', 0)))
            vat_amount = sale.tax_amount or Decimal('0')

            output_vat += vat_amount
            total_sales += sale.gross_amount

            rate_key = f"{vat_rate}%"
            if rate_key not in sales_by_rate:
                sales_by_rate[rate_key] = {
                    'rate': vat_rate,
                    'net_sales': Decimal('0'),
                    'vat_amount': Decimal('0')
                }

            sales_by_rate[rate_key]['net_sales'] += sale.net_amount
            sales_by_rate[rate_key]['vat_amount'] += vat_amount

        # Calculate input VAT (VAT paid on purchases)
        input_vat = Decimal('0')
        total_purchases = Decimal('0')
        purchases_by_rate = {}

        for purchase in purchases:
            vat_rate = Decimal(str(purchase.metadata.get('vat_rate', 0)))
            vat_amount = purchase.tax_amount or Decimal('0')

            # Check if VAT is reclaimable
            is_reclaimable = purchase.metadata.get('vat_reclaimable', True)

            if is_reclaimable:
                input_vat += vat_amount

            total_purchases += purchase.gross_amount

            rate_key = f"{vat_rate}%"
            if rate_key not in purchases_by_rate:
                purchases_by_rate[rate_key] = {
                    'rate': vat_rate,
                    'net_purchases': Decimal('0'),
                    'vat_amount': Decimal('0'),
                    'reclaimable_vat': Decimal('0')
                }

            purchases_by_rate[rate_key]['net_purchases'] += purchase.net_amount
            purchases_by_rate[rate_key]['vat_amount'] += vat_amount

            if is_reclaimable:
                purchases_by_rate[rate_key]['reclaimable_vat'] += vat_amount

        # Calculate net VAT payable/reclaimable
        net_vat = output_vat - input_vat

        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'vat_scheme': vat_scheme,
            'output_vat': {
                'total': float(output_vat),
                'total_sales': float(total_sales),
                'by_rate': [
                    {**data, 'net_sales': float(data['net_sales']), 'vat_amount': float(data['vat_amount'])}
                    for data in sales_by_rate.values()
                ]
            },
            'input_vat': {
                'total': float(input_vat),
                'total_purchases': float(total_purchases),
                'by_rate': [
                    {
                        **data,
                        'net_purchases': float(data['net_purchases']),
                        'vat_amount': float(data['vat_amount']),
                        'reclaimable_vat': float(data['reclaimable_vat'])
                    }
                    for data in purchases_by_rate.values()
                ]
            },
            'net_vat': float(net_vat),
            'status': 'payable' if net_vat > 0 else 'reclaimable' if net_vat < 0 else 'nil'
        }

    def generate_1099_report(
        self,
        tax_year: int,
        form_type: str = '1099-NEC'
    ) -> List[Dict]:
        """
        Generate 1099 report for vendors/contractors.

        Args:
            tax_year: Tax year for reporting
            form_type: Type of 1099 form (1099-NEC, 1099-MISC, 1099-K)

        Returns:
            List of vendors requiring 1099 forms
        """
        start_date = date(tax_year, 1, 1)
        end_date = date(tax_year, 12, 31)

        # Get payments to vendors/contractors
        # In production, you'd have a Vendor model with 1099 eligibility flag
        vendor_payments = {}

        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='expense',
            metadata__requires_1099=True  # Flag indicating 1099-eligible expense
        )

        for txn in transactions:
            vendor_id = txn.metadata.get('vendor_id', 'unknown')
            vendor_name = txn.metadata.get('vendor_name', txn.customer_name or 'Unknown')
            vendor_tin = txn.metadata.get('vendor_tin', '')

            if vendor_id not in vendor_payments:
                vendor_payments[vendor_id] = {
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'vendor_tin': vendor_tin,
                    'total_payments': Decimal('0'),
                    'transaction_count': 0,
                    'payment_breakdown': {
                        'services': Decimal('0'),  # Box 1 for 1099-NEC
                        'rent': Decimal('0'),
                        'royalties': Decimal('0'),
                        'other_income': Decimal('0')
                    }
                }

            vendor_data = vendor_payments[vendor_id]
            vendor_data['total_payments'] += txn.gross_amount
            vendor_data['transaction_count'] += 1

            # Categorize payment type
            payment_category = txn.metadata.get('1099_category', 'services')
            if payment_category in vendor_data['payment_breakdown']:
                vendor_data['payment_breakdown'][payment_category] += txn.gross_amount

        # Filter vendors meeting 1099 threshold
        threshold = Decimal('600.00')  # IRS threshold for 1099-NEC

        vendors_requiring_1099 = []
        for vendor_data in vendor_payments.values():
            if vendor_data['total_payments'] >= threshold:
                # Convert Decimals to floats for JSON serialization
                vendor_data['total_payments'] = float(vendor_data['total_payments'])
                vendor_data['payment_breakdown'] = {
                    k: float(v) for k, v in vendor_data['payment_breakdown'].items()
                }
                vendors_requiring_1099.append(vendor_data)

        # Sort by total payments descending
        vendors_requiring_1099.sort(key=lambda x: x['total_payments'], reverse=True)

        return {
            'tax_year': tax_year,
            'form_type': form_type,
            'vendor_count': len(vendors_requiring_1099),
            'total_reportable_payments': sum(v['total_payments'] for v in vendors_requiring_1099),
            'threshold': float(threshold),
            'vendors': vendors_requiring_1099
        }

    def calculate_nexus_by_state(
        self,
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Calculate sales tax nexus by state.

        Nexus determination helps identify states where business has tax obligations.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dict with sales by state and nexus indicators
        """
        transactions = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='sale'
        )

        states = {}

        for txn in transactions:
            # Get state from shipping or billing address
            state = txn.metadata.get('shipping_state') or txn.metadata.get('billing_state', 'Unknown')

            if state not in states:
                states[state] = {
                    'state': state,
                    'total_sales': Decimal('0'),
                    'taxable_sales': Decimal('0'),
                    'tax_collected': Decimal('0'),
                    'transaction_count': 0,
                    'customer_count': set()
                }

            state_data = states[state]
            state_data['total_sales'] += txn.gross_amount
            state_data['transaction_count'] += 1

            if txn.customer_name:
                state_data['customer_count'].add(txn.customer_name)

            is_taxable = txn.metadata.get('is_taxable', True)
            if is_taxable:
                state_data['taxable_sales'] += txn.net_amount
                state_data['tax_collected'] += txn.tax_amount or Decimal('0')

        # Economic nexus thresholds (common thresholds, vary by state)
        economic_nexus_threshold_sales = Decimal('100000')  # $100k in sales
        economic_nexus_threshold_transactions = 200  # 200 transactions

        results = []
        for state_code, data in states.items():
            customer_count = len(data['customer_count'])

            # Determine if nexus likely exists
            has_economic_nexus = (
                data['total_sales'] >= economic_nexus_threshold_sales or
                data['transaction_count'] >= economic_nexus_threshold_transactions
            )

            results.append({
                'state': state_code,
                'total_sales': float(data['total_sales']),
                'taxable_sales': float(data['taxable_sales']),
                'tax_collected': float(data['tax_collected']),
                'transaction_count': data['transaction_count'],
                'customer_count': customer_count,
                'has_economic_nexus': has_economic_nexus,
                'nexus_reason': 'Economic nexus threshold met' if has_economic_nexus else 'Below threshold'
            })

        # Sort by total sales descending
        results.sort(key=lambda x: x['total_sales'], reverse=True)

        return {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'states': results,
            'states_with_nexus': [r for r in results if r['has_economic_nexus']],
            'nexus_count': len([r for r in results if r['has_economic_nexus']])
        }

    def calculate_quarterly_estimated_tax(
        self,
        year: int,
        quarter: int
    ) -> Dict:
        """
        Calculate quarterly estimated tax payment.

        Args:
            year: Tax year
            quarter: Quarter (1-4)

        Returns:
            Dict with estimated tax calculation
        """
        # Determine quarter dates
        quarter_dates = {
            1: (date(year, 1, 1), date(year, 3, 31)),
            2: (date(year, 4, 1), date(year, 6, 30)),
            3: (date(year, 7, 1), date(year, 9, 30)),
            4: (date(year, 10, 1), date(year, 12, 31)),
        }

        start_date, end_date = quarter_dates[quarter]

        # Calculate income and expenses
        income = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='sale'
        ).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0')

        expenses = Transaction.objects.filter(
            organization=self.organization,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
            transaction_type='expense'
        ).aggregate(total=Sum('gross_amount'))['total'] or Decimal('0')

        # Calculate net income
        net_income = income - expenses

        # Estimated tax rate (simplified - in production use actual tax brackets)
        # Federal: 15.3% self-employment + 22% income = ~37%
        estimated_tax_rate = Decimal('0.37')

        estimated_tax = net_income * estimated_tax_rate

        # Quarterly payment (divide annual estimate by 4)
        quarterly_payment = estimated_tax

        return {
            'year': year,
            'quarter': quarter,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'gross_income': float(income),
            'total_expenses': float(expenses),
            'net_income': float(net_income),
            'estimated_tax_rate': float(estimated_tax_rate),
            'estimated_tax': float(estimated_tax),
            'quarterly_payment': float(quarterly_payment),
            'due_date': self._get_estimated_tax_due_date(year, quarter)
        }

    def _get_estimated_tax_due_date(self, year: int, quarter: int) -> str:
        """
        Get IRS estimated tax due date for a quarter.

        Args:
            year: Tax year
            quarter: Quarter (1-4)

        Returns:
            Due date as ISO string
        """
        due_dates = {
            1: date(year, 4, 15),
            2: date(year, 6, 15),
            3: date(year, 9, 15),
            4: date(year + 1, 1, 15),
        }

        return due_dates[quarter].isoformat()

    def get_tax_compliance_checklist(
        self,
        year: int
    ) -> Dict:
        """
        Generate tax compliance checklist for the year.

        Args:
            year: Tax year

        Returns:
            Dict with compliance status and required actions
        """
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        checklist_items = []

        # Check 1099 requirements
        form_1099 = self.generate_1099_report(year)
        checklist_items.append({
            'category': '1099 Reporting',
            'status': 'required' if form_1099['vendor_count'] > 0 else 'not_required',
            'description': f"{form_1099['vendor_count']} vendors require 1099 forms",
            'due_date': date(year + 1, 1, 31).isoformat(),
            'action': 'File 1099-NEC forms' if form_1099['vendor_count'] > 0 else None
        })

        # Check sales tax nexus
        nexus = self.calculate_nexus_by_state(start_date, end_date)
        checklist_items.append({
            'category': 'Sales Tax Nexus',
            'status': 'action_required' if nexus['nexus_count'] > 0 else 'compliant',
            'description': f"Economic nexus in {nexus['nexus_count']} states",
            'action': 'Register for sales tax collection' if nexus['nexus_count'] > 0 else None
        })

        # Check quarterly estimated tax payments
        for quarter in range(1, 5):
            quarterly = self.calculate_quarterly_estimated_tax(year, quarter)
            if quarterly['estimated_tax'] > 0:
                checklist_items.append({
                    'category': f'Q{quarter} Estimated Tax',
                    'status': 'pending',
                    'description': f"Estimated payment: ${quarterly['quarterly_payment']:.2f}",
                    'due_date': quarterly['due_date'],
                    'action': 'Make quarterly estimated tax payment'
                })

        # Annual tax return
        checklist_items.append({
            'category': 'Annual Tax Return',
            'status': 'pending',
            'description': 'File annual tax return (Form 1040)',
            'due_date': date(year + 1, 4, 15).isoformat(),
            'action': 'File tax return'
        })

        return {
            'tax_year': year,
            'checklist': checklist_items,
            'total_items': len(checklist_items),
            'action_required_count': len([i for i in checklist_items if i.get('action')])
        }
