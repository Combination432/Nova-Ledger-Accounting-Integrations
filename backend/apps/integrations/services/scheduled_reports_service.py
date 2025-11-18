"""
Scheduled reports service.
Handles automatic report generation and email delivery.
"""
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
from django.core.mail import EmailMessage
from django.utils import timezone
from .export_service import ExportService
from .tax_service import TaxService
from .analytics_service import AnalyticsService
import logging

logger = logging.getLogger(__name__)


class ScheduledReportsService:
    """
    Service for scheduling and delivering automated reports.
    """

    def __init__(self, organization):
        """
        Initialize scheduled reports service.

        Args:
            organization: Organization object
        """
        self.organization = organization
        self.export_service = ExportService(organization)
        self.tax_service = TaxService(organization)
        self.analytics_service = AnalyticsService(organization)

    def create_schedule(
        self,
        report_type: str,
        frequency: str,
        recipients: List[str],
        format: str = 'excel',
        parameters: Optional[Dict] = None
    ) -> Dict:
        """
        Create a report schedule.

        Args:
            report_type: Type of report (transactions, tax, analytics, etc.)
            frequency: Schedule frequency (daily, weekly, monthly, quarterly)
            recipients: List of email addresses
            format: Report format (excel, csv, pdf)
            parameters: Additional report parameters

        Returns:
            Created schedule
        """
        schedule = {
            'id': timezone.now().timestamp(),  # In production, use UUID
            'organization_id': str(self.organization.id),
            'report_type': report_type,
            'frequency': frequency,
            'recipients': recipients,
            'format': format,
            'parameters': parameters or {},
            'is_active': True,
            'created_at': timezone.now().isoformat(),
            'next_run': self._calculate_next_run(frequency).isoformat()
        }

        # In production, save to ScheduledReport model
        logger.info(f"Created report schedule: {report_type} - {frequency}")

        return schedule

    def execute_scheduled_report(
        self,
        schedule_id: str
    ) -> Dict:
        """
        Execute a scheduled report and send via email.

        Args:
            schedule_id: Schedule ID

        Returns:
            Execution results
        """
        # In production, load from ScheduledReport model
        # For now, use example
        schedule = {
            'report_type': 'transactions',
            'format': 'excel',
            'recipients': ['user@example.com'],
            'parameters': {}
        }

        try:
            # Generate report
            report_data = self._generate_report(
                schedule['report_type'],
                schedule['parameters']
            )

            # Export to file
            file_buffer, filename = self._export_report(
                report_data,
                schedule['format'],
                schedule['report_type']
            )

            # Send email
            self._send_report_email(
                recipients=schedule['recipients'],
                report_type=schedule['report_type'],
                file_buffer=file_buffer,
                filename=filename,
                format=schedule['format']
            )

            # Update schedule
            # schedule.last_run = timezone.now()
            # schedule.next_run = self._calculate_next_run(schedule.frequency)
            # schedule.save()

            return {
                'status': 'success',
                'executed_at': timezone.now().isoformat(),
                'recipients': schedule['recipients'],
                'filename': filename
            }

        except Exception as e:
            logger.error(f"Failed to execute scheduled report: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e),
                'executed_at': timezone.now().isoformat()
            }

    def _generate_report(
        self,
        report_type: str,
        parameters: Dict
    ):
        """
        Generate report data.

        Args:
            report_type: Type of report
            parameters: Report parameters

        Returns:
            Report data
        """
        # Calculate date range based on frequency
        end_date = timezone.now().date()
        start_date = parameters.get('start_date')

        if not start_date:
            # Default to last month
            start_date = (end_date.replace(day=1) - timedelta(days=1)).replace(day=1)

        if report_type == 'transactions':
            from apps.transactions.models import Transaction
            return Transaction.objects.filter(
                organization=self.organization,
                transaction_date__gte=start_date,
                transaction_date__lte=end_date
            )

        elif report_type == 'tax_summary':
            return self.tax_service.calculate_sales_tax_summary(
                start_date,
                end_date
            )

        elif report_type == 'analytics':
            return self.analytics_service.get_dashboard_kpis(
                start_date,
                end_date
            )

        else:
            raise ValueError(f"Unknown report type: {report_type}")

    def _export_report(
        self,
        report_data,
        format: str,
        report_type: str
    ):
        """
        Export report to file format.

        Args:
            report_data: Report data
            format: Export format
            report_type: Report type

        Returns:
            Tuple of (file_buffer, filename)
        """
        timestamp = timezone.now().strftime('%Y%m%d')

        if format == 'excel':
            if report_type == 'transactions':
                return self.export_service.export_transactions_excel(
                    report_data,
                    f"{report_type}_{timestamp}.xlsx"
                )
            else:
                # For other reports, create simple Excel
                import openpyxl
                from io import BytesIO

                wb = openpyxl.Workbook()
                ws = wb.active
                ws['A1'] = 'Report Data'
                ws['A2'] = str(report_data)

                buffer = BytesIO()
                wb.save(buffer)
                buffer.seek(0)

                return buffer, f"{report_type}_{timestamp}.xlsx"

        elif format == 'csv':
            if report_type == 'transactions':
                return self.export_service.export_transactions_csv(
                    report_data,
                    f"{report_type}_{timestamp}.csv"
                )
            else:
                # Simple CSV export
                from io import BytesIO
                import csv

                buffer = BytesIO()
                writer = csv.writer(buffer)
                writer.writerow(['Report', 'Data'])
                writer.writerow([report_type, str(report_data)])
                buffer.seek(0)

                return buffer, f"{report_type}_{timestamp}.csv"

        else:
            raise ValueError(f"Unsupported format: {format}")

    def _send_report_email(
        self,
        recipients: List[str],
        report_type: str,
        file_buffer,
        filename: str,
        format: str
    ):
        """
        Send report via email.

        Args:
            recipients: List of email recipients
            report_type: Type of report
            file_buffer: File buffer
            filename: Attachment filename
            format: File format
        """
        subject = f"Scheduled Report: {report_type.replace('_', ' ').title()}"

        body = f"""
        Your scheduled {report_type.replace('_', ' ')} report is attached.

        Report Details:
        - Type: {report_type}
        - Format: {format.upper()}
        - Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

        This is an automated report from Nova Ledger.
        """

        # Determine content type
        content_types = {
            'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'csv': 'text/csv',
            'pdf': 'application/pdf'
        }

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email='noreply@novaledger.com',
            to=recipients
        )

        email.attach(
            filename,
            file_buffer.getvalue(),
            content_types.get(format, 'application/octet-stream')
        )

        # In production, this would actually send
        # email.send()

        logger.info(f"Would send report email to {recipients} with attachment {filename}")

    def _calculate_next_run(self, frequency: str) -> datetime:
        """
        Calculate next run time based on frequency.

        Args:
            frequency: Schedule frequency

        Returns:
            Next run datetime
        """
        now = timezone.now()

        if frequency == 'daily':
            # Run at 6 AM next day
            next_run = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)

        elif frequency == 'weekly':
            # Run on Monday at 6 AM
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_run = (now + timedelta(days=days_until_monday)).replace(hour=6, minute=0, second=0, microsecond=0)

        elif frequency == 'monthly':
            # Run on 1st of next month at 6 AM
            if now.month == 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, hour=6, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=now.month + 1, day=1, hour=6, minute=0, second=0, microsecond=0)

        elif frequency == 'quarterly':
            # Run on first day of next quarter at 6 AM
            current_quarter = (now.month - 1) // 3
            next_quarter_month = (current_quarter + 1) * 3 + 1

            if next_quarter_month > 12:
                next_run = now.replace(year=now.year + 1, month=1, day=1, hour=6, minute=0, second=0, microsecond=0)
            else:
                next_run = now.replace(month=next_quarter_month, day=1, hour=6, minute=0, second=0, microsecond=0)

        else:
            # Default to daily
            next_run = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)

        return next_run

    def get_schedules(self) -> List[Dict]:
        """
        Get all active schedules for organization.

        Returns:
            List of schedules
        """
        # In production, query from ScheduledReport model
        return [
            {
                'id': '1',
                'report_type': 'transactions',
                'frequency': 'monthly',
                'format': 'excel',
                'recipients': ['user@example.com'],
                'next_run': self._calculate_next_run('monthly').isoformat()
            }
        ]

    def delete_schedule(self, schedule_id: str) -> bool:
        """
        Delete a report schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            True if successful
        """
        # In production, delete from ScheduledReport model
        logger.info(f"Deleted schedule: {schedule_id}")
        return True
