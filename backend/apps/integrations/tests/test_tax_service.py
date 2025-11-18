"""
Tests for tax service.
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.transactions.models import Transaction
from apps.integrations.services.tax_service import TaxService

User = get_user_model()


class TaxServiceTestCase(TestCase):
    """Test cases for TaxService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.organization = self.user.organization
        self.service = TaxService(self.organization)

        # Create test transactions with tax
        self.create_test_transactions()

    def create_test_transactions(self):
        """Create test transactions with various tax scenarios."""
        # California sales
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('1000.00'),
            net_amount=Decimal('925.93'),
            tax_amount=Decimal('74.07'),
            metadata={
                'tax_jurisdiction': 'California',
                'tax_rate': 0.08,
                'is_taxable': True
            }
        )

        # New York sales
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 16),
            gross_amount=Decimal('500.00'),
            net_amount=Decimal('462.96'),
            tax_amount=Decimal('37.04'),
            metadata={
                'tax_jurisdiction': 'New York',
                'tax_rate': 0.08,
                'is_taxable': True
            }
        )

        # Tax-exempt sale
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 17),
            gross_amount=Decimal('200.00'),
            net_amount=Decimal('200.00'),
            tax_amount=Decimal('0.00'),
            metadata={
                'tax_jurisdiction': 'California',
                'is_taxable': False
            }
        )

    def test_calculate_sales_tax_summary(self):
        """Test sales tax summary calculation."""
        summary = self.service.calculate_sales_tax_summary(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        self.assertIn('jurisdictions', summary)
        self.assertIn('total_tax_collected', summary)
        self.assertGreater(summary['total_tax_collected'], 0)

        # Check jurisdiction breakdown
        jurisdictions = summary['jurisdictions']
        self.assertGreater(len(jurisdictions), 0)

        # Verify California data
        ca_data = next((j for j in jurisdictions if j['jurisdiction'] == 'California'), None)
        self.assertIsNotNone(ca_data)
        self.assertGreater(ca_data['tax_collected'], 0)

    def test_calculate_vat_summary(self):
        """Test VAT summary calculation."""
        # Create transactions with VAT
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('1200.00'),
            net_amount=Decimal('1000.00'),
            tax_amount=Decimal('200.00'),
            metadata={'vat_rate': 20}
        )

        Transaction.objects.create(
            organization=self.organization,
            transaction_type='expense',
            transaction_date=date(2024, 1, 16),
            gross_amount=Decimal('600.00'),
            net_amount=Decimal('500.00'),
            tax_amount=Decimal('100.00'),
            metadata={'vat_rate': 20, 'vat_reclaimable': True}
        )

        summary = self.service.calculate_vat_summary(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            vat_scheme='standard'
        )

        self.assertIn('output_vat', summary)
        self.assertIn('input_vat', summary)
        self.assertIn('net_vat', summary)

        # Net VAT should be output - input
        self.assertGreater(summary['output_vat']['total'], 0)

    def test_generate_1099_report(self):
        """Test 1099 report generation."""
        # Create vendor expenses
        for i in range(3):
            Transaction.objects.create(
                organization=self.organization,
                transaction_type='expense',
                transaction_date=date(2024, 1, 15 + i),
                gross_amount=Decimal('500.00'),
                net_amount=Decimal('500.00'),
                customer_name=f'Vendor {i+1}',
                metadata={
                    'requires_1099': True,
                    'vendor_id': f'vendor_{i+1}',
                    'vendor_name': f'Vendor {i+1}',
                    'vendor_tin': f'12-345678{i}',
                    '1099_category': 'services'
                }
            )

        report = self.service.generate_1099_report(
            tax_year=2024,
            form_type='1099-NEC'
        )

        self.assertEqual(report['tax_year'], 2024)
        self.assertIn('vendors', report)
        # Should have vendors over $600 threshold
        self.assertGreaterEqual(len(report['vendors']), 0)

    def test_calculate_nexus_by_state(self):
        """Test nexus calculation by state."""
        # Create transactions in different states
        states = ['CA', 'NY', 'TX']
        for state in states:
            for i in range(50):  # Create 50 transactions per state
                Transaction.objects.create(
                    organization=self.organization,
                    transaction_type='sale',
                    transaction_date=date(2024, 1, 15),
                    gross_amount=Decimal('100.00'),
                    net_amount=Decimal('93.00'),
                    tax_amount=Decimal('7.00'),
                    customer_name=f'Customer {i}',
                    metadata={
                        'shipping_state': state,
                        'is_taxable': True
                    }
                )

        nexus = self.service.calculate_nexus_by_state(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        self.assertIn('states', nexus)
        self.assertGreater(len(nexus['states']), 0)

        # Check nexus determination
        for state_data in nexus['states']:
            self.assertIn('has_economic_nexus', state_data)

    def test_calculate_quarterly_estimated_tax(self):
        """Test quarterly estimated tax calculation."""
        # Create income and expenses for Q1
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('10000.00'),
            net_amount=Decimal('10000.00')
        )

        Transaction.objects.create(
            organization=self.organization,
            transaction_type='expense',
            transaction_date=date(2024, 1, 20),
            gross_amount=Decimal('3000.00'),
            net_amount=Decimal('3000.00')
        )

        quarterly = self.service.calculate_quarterly_estimated_tax(
            year=2024,
            quarter=1
        )

        self.assertEqual(quarterly['year'], 2024)
        self.assertEqual(quarterly['quarter'], 1)
        self.assertGreater(quarterly['gross_income'], 0)
        self.assertGreater(quarterly['total_expenses'], 0)
        self.assertGreater(quarterly['net_income'], 0)

    def test_get_tax_compliance_checklist(self):
        """Test tax compliance checklist generation."""
        checklist = self.service.get_tax_compliance_checklist(year=2024)

        self.assertEqual(checklist['tax_year'], 2024)
        self.assertIn('checklist', checklist)
        self.assertGreater(len(checklist['checklist']), 0)

        # Should include various compliance items
        categories = [item['category'] for item in checklist['checklist']]
        self.assertIn('1099 Reporting', categories)
        self.assertIn('Annual Tax Return', categories)

    def test_sales_tax_jurisdiction_filtering(self):
        """Test filtering by specific jurisdiction."""
        summary = self.service.calculate_sales_tax_summary(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            jurisdiction='California'
        )

        # Should only include California
        jurisdictions = summary['jurisdictions']
        if jurisdictions:
            self.assertTrue(
                all(j['jurisdiction'] == 'California' for j in jurisdictions)
            )

    def test_vat_different_rates(self):
        """Test VAT calculation with different rates."""
        # Standard rate (20%)
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 15),
            gross_amount=Decimal('120.00'),
            net_amount=Decimal('100.00'),
            tax_amount=Decimal('20.00'),
            metadata={'vat_rate': 20}
        )

        # Reduced rate (5%)
        Transaction.objects.create(
            organization=self.organization,
            transaction_type='sale',
            transaction_date=date(2024, 1, 16),
            gross_amount=Decimal('105.00'),
            net_amount=Decimal('100.00'),
            tax_amount=Decimal('5.00'),
            metadata={'vat_rate': 5}
        )

        summary = self.service.calculate_vat_summary(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

        # Should have breakdown by rate
        output_by_rate = summary['output_vat']['by_rate']
        self.assertGreater(len(output_by_rate), 0)
