"""
Data export service for reports and data downloads.
Supports Excel, CSV, and PDF formats.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime
from io import BytesIO
import csv
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting data in various formats.
    """

    def __init__(self, organization):
        self.organization = organization

    def export_transactions_csv(
        self,
        transactions,
        filename: str = 'transactions.csv'
    ) -> tuple[BytesIO, str]:
        """
        Export transactions to CSV format.

        Args:
            transactions: QuerySet or list of transactions
            filename: Output filename

        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        output = BytesIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Transaction ID',
            'Date',
            'Description',
            'Type',
            'Gross Amount',
            'Net Amount',
            'Currency',
            'Customer Name',
            'Customer Email',
            'Source Platform',
            'Status'
        ])

        # Write data
        for txn in transactions:
            writer.writerow([
                str(txn.id),
                txn.transaction_date.isoformat() if txn.transaction_date else '',
                txn.description or '',
                txn.transaction_type or '',
                str(txn.gross_amount),
                str(txn.net_amount),
                txn.currency or '',
                txn.customer_name or '',
                txn.customer_email or '',
                txn.source_platform or '',
                txn.metadata.get('status', '') if txn.metadata else ''
            ])

        output.seek(0)
        return output, filename

    def export_transactions_excel(
        self,
        transactions,
        filename: str = 'transactions.xlsx'
    ) -> tuple[BytesIO, str]:
        """
        Export transactions to Excel format.

        Args:
            transactions: QuerySet or list of transactions
            filename: Output filename

        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill
        except ImportError:
            logger.error("openpyxl not installed")
            raise ImportError("openpyxl is required for Excel export")

        # Create workbook
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Transactions"

        # Header style
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        header_alignment = Alignment(horizontal="center", vertical="center")

        # Write header
        headers = [
            'Transaction ID', 'Date', 'Description', 'Type',
            'Gross Amount', 'Net Amount', 'Currency',
            'Customer Name', 'Customer Email', 'Source Platform', 'Status'
        ]

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment

        # Write data
        for row_num, txn in enumerate(transactions, 2):
            ws.cell(row=row_num, column=1, value=str(txn.id))
            ws.cell(row=row_num, column=2, value=txn.transaction_date.isoformat() if txn.transaction_date else '')
            ws.cell(row=row_num, column=3, value=txn.description or '')
            ws.cell(row=row_num, column=4, value=txn.transaction_type or '')
            ws.cell(row=row_num, column=5, value=float(txn.gross_amount))
            ws.cell(row=row_num, column=6, value=float(txn.net_amount))
            ws.cell(row=row_num, column=7, value=txn.currency or '')
            ws.cell(row=row_num, column=8, value=txn.customer_name or '')
            ws.cell(row=row_num, column=9, value=txn.customer_email or '')
            ws.cell(row=row_num, column=10, value=txn.source_platform or '')
            ws.cell(row=row_num, column=11, value=txn.metadata.get('status', '') if txn.metadata else '')

        # Auto-size columns
        for column in ws.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = min(adjusted_width, 50)

        # Save to BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output, filename

    def export_reconciliation_report_excel(
        self,
        reconciliation,
        filename: str = 'reconciliation_report.xlsx'
    ) -> tuple[BytesIO, str]:
        """
        Export reconciliation report to Excel.

        Args:
            reconciliation: BankReconciliation object
            filename: Output filename

        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        except ImportError:
            raise ImportError("openpyxl is required for Excel export")

        wb = openpyxl.Workbook()

        # Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Summary"

        # Title
        ws_summary['A1'] = f"Bank Reconciliation Report"
        ws_summary['A1'].font = Font(size=16, bold=True)
        ws_summary.merge_cells('A1:D1')

        # Period
        ws_summary['A3'] = "Period:"
        ws_summary['B3'] = f"{reconciliation.period_start} to {reconciliation.period_end}"

        # Bank account
        ws_summary['A4'] = "Bank Account:"
        ws_summary['B4'] = reconciliation.bank_account.account_name

        # Status
        ws_summary['A5'] = "Status:"
        ws_summary['B5'] = reconciliation.status.upper()

        # Statistics
        ws_summary['A7'] = "Statistics"
        ws_summary['A7'].font = Font(bold=True)

        ws_summary['A8'] = "Opening Balance:"
        ws_summary['B8'] = float(reconciliation.opening_balance)

        ws_summary['A9'] = "Closing Balance:"
        ws_summary['B9'] = float(reconciliation.closing_balance)

        ws_summary['A10'] = "Matched Transactions:"
        ws_summary['B10'] = reconciliation.total_matched

        ws_summary['A11'] = "Suggested Matches:"
        ws_summary['B11'] = reconciliation.total_suggested

        ws_summary['A12'] = "Unmatched Transactions:"
        ws_summary['B12'] = reconciliation.total_unmatched

        # Matches sheet
        ws_matches = wb.create_sheet(title="Matches")

        # Header
        headers = ['Match Type', 'Confidence', 'Bank Date', 'Bank Amount', 'Bank Description',
                   'Transaction Date', 'Transaction Amount', 'Transaction Description', 'Status']

        for col_num, header in enumerate(headers, 1):
            cell = ws_matches.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)

        # Data
        from ..models import ReconciliationMatch
        matches = ReconciliationMatch.objects.filter(reconciliation=reconciliation).select_related(
            'bank_transaction'
        ).prefetch_related('transactions')

        for row_num, match in enumerate(matches, 2):
            ws_matches.cell(row=row_num, column=1, value=match.match_type)
            ws_matches.cell(row=row_num, column=2, value=float(match.confidence_score))
            ws_matches.cell(row=row_num, column=3, value=match.bank_transaction.transaction_date.isoformat())
            ws_matches.cell(row=row_num, column=4, value=float(match.bank_transaction.amount))
            ws_matches.cell(row=row_num, column=5, value=match.bank_transaction.description or '')

            # First matched transaction
            txn = match.transactions.first()
            if txn:
                ws_matches.cell(row=row_num, column=6, value=txn.transaction_date.isoformat() if txn.transaction_date else '')
                ws_matches.cell(row=row_num, column=7, value=float(txn.gross_amount))
                ws_matches.cell(row=row_num, column=8, value=txn.description or '')

            ws_matches.cell(row=row_num, column=9, value='Confirmed' if match.is_confirmed else 'Suggested')

        # Save
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output, filename

    def export_tax_report_excel(
        self,
        start_date: date,
        end_date: date,
        filename: str = 'tax_report.xlsx'
    ) -> tuple[BytesIO, str]:
        """
        Export tax report to Excel.

        Args:
            start_date: Report start date
            end_date: Report end date
            filename: Output filename

        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            raise ImportError("openpyxl is required for Excel export")

        from apps.transactions.models import Transaction
        from ..models import TaxConfiguration

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Tax Report"

        # Title
        ws['A1'] = f"Tax Report: {start_date} to {end_date}"
        ws['A1'].font = Font(size=16, bold=True)
        ws.merge_cells('A1:F1')

        # Get taxconfigurations
        tax_configs = TaxConfiguration.objects.filter(
            organization=self.organization,
            is_active=True
        )

        row = 3
        for tax_config in tax_configs:
            # Header for each tax jurisdiction
            ws.cell(row=row, column=1, value=tax_config.tax_name).font = Font(bold=True)
            ws.cell(row=row, column=2, value=f"{tax_config.tax_rate * 100}%")
            row += 1

            # Get transactions with this tax
            # This is simplified - in a real implementation, you'd need to track tax per transaction
            transactions = Transaction.objects.filter(
                organization=self.organization,
                transaction_date__gte=start_date,
                transaction_date__lte=end_date
            )

            # Summary row
            ws.cell(row=row, column=1, value="Total Taxable Sales:")
            # In production, calculate actual taxable amount
            total_sales = sum(txn.gross_amount for txn in transactions)
            ws.cell(row=row, column=2, value=float(total_sales))

            ws.cell(row=row, column=3, value="Tax Collected:")
            tax_collected = total_sales * tax_config.tax_rate
            ws.cell(row=row, column=4, value=float(tax_collected))

            row += 2

        # Save
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output, filename

    def export_forex_report_excel(
        self,
        start_date: date,
        end_date: date,
        filename: str = 'forex_report.xlsx'
    ) -> tuple[BytesIO, str]:
        """
        Export forex gains/losses report to Excel.

        Args:
            start_date: Report start date
            end_date: Report end date
            filename: Output filename

        Returns:
            Tuple of (BytesIO buffer, filename)
        """
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            raise ImportError("openpyxl is required for Excel export")

        from ..models import ForexGainLoss

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Forex Gains/Losses"

        # Title
        ws['A1'] = f"Forex Gains/Losses Report: {start_date} to {end_date}"
        ws['A1'].font = Font(size=16, bold=True)
        ws.merge_cells('A1:H1')

        # Headers
        headers = ['Date', 'Type', 'From Currency', 'To Currency', 'Original Amount',
                   'Converted Amount', 'Gain/Loss', 'Original Rate', 'Current Rate']

        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_num, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)

        # Data
        forex_records = ForexGainLoss.objects.filter(
            organization=self.organization,
            calculation_date__gte=start_date,
            calculation_date__lte=end_date
        ).order_by('calculation_date')

        total_gains = Decimal('0')
        total_losses = Decimal('0')

        for row_num, record in enumerate(forex_records, 4):
            ws.cell(row=row_num, column=1, value=record.calculation_date.isoformat())
            ws.cell(row=row_num, column=2, value=record.gain_loss_type.title())
            ws.cell(row=row_num, column=3, value=record.from_currency.code)
            ws.cell(row=row_num, column=4, value=record.to_currency.code)
            ws.cell(row=row_num, column=5, value=float(record.original_amount))
            ws.cell(row=row_num, column=6, value=float(record.converted_amount))
            ws.cell(row=row_num, column=7, value=float(record.gain_loss_amount))
            ws.cell(row=row_num, column=8, value=float(record.original_rate))
            ws.cell(row=row_num, column=9, value=float(record.current_rate))

            if record.gain_loss_amount > 0:
                total_gains += record.gain_loss_amount
            else:
                total_losses += abs(record.gain_loss_amount)

        # Summary
        summary_row = len(forex_records) + 5
        ws.cell(row=summary_row, column=1, value="Summary:").font = Font(bold=True)
        ws.cell(row=summary_row + 1, column=1, value="Total Gains:")
        ws.cell(row=summary_row + 1, column=2, value=float(total_gains))
        ws.cell(row=summary_row + 2, column=1, value="Total Losses:")
        ws.cell(row=summary_row + 2, column=2, value=float(total_losses))
        ws.cell(row=summary_row + 3, column=1, value="Net Gain/Loss:")
        ws.cell(row=summary_row + 3, column=2, value=float(total_gains - total_losses))

        # Save
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output, filename
