"""
Tax calculation engine for Nova Ledger.
Handles multi-jurisdictional sales tax calculation with nexus tracking.
"""
from decimal import Decimal
from typing import Dict, List, Tuple
from django.db.models import Q
from .models import TaxConfiguration
import logging

logger = logging.getLogger(__name__)


class TaxCalculationEngine:
    """
    Advanced tax calculation engine supporting:
    - US sales tax (state + local)
    - Canadian GST/HST/PST
    - Multi-jurisdictional tax
    - Nexus tracking
    - Product exemptions
    """

    def __init__(self, organization):
        self.organization = organization

    def calculate_sales_tax(
        self,
        amount: Decimal,
        origin_address: Dict[str, str],
        destination_address: Dict[str, str],
        product_tax_code: str = 'default',
        is_shipping_taxable: bool = False
    ) -> Dict[str, any]:
        """
        Calculate sales tax for a transaction.

        Args:
            amount: Transaction amount
            origin_address: Dict with keys: country, state, city, postal_code
            destination_address: Destination address
            product_tax_code: Product tax classification
            is_shipping_taxable: Whether shipping is taxable

        Returns:
            Dict with tax_amount, tax_rate, applied_taxes, nexus_required
        """
        # Determine tax jurisdiction (origin vs destination-based)
        tax_jurisdiction = self._determine_jurisdiction(
            origin_address,
            destination_address
        )

        # Check nexus
        has_nexus = self._check_nexus(tax_jurisdiction)

        if not has_nexus:
            logger.info(
                f"No nexus in {tax_jurisdiction.get('state')}, "
                f"{tax_jurisdiction.get('country')}. No tax applied."
            )
            return {
                'tax_amount': Decimal('0'),
                'tax_rate': Decimal('0'),
                'applied_taxes': [],
                'nexus_required': False,
                'jurisdiction': tax_jurisdiction
            }

        # Get applicable tax rates
        tax_configs = self._get_applicable_taxes(
            tax_jurisdiction,
            product_tax_code
        )

        if not tax_configs:
            logger.warning(
                f"No tax configuration found for {tax_jurisdiction}. "
                f"Defaulting to 0% tax."
            )
            return {
                'tax_amount': Decimal('0'),
                'tax_rate': Decimal('0'),
                'applied_taxes': [],
                'nexus_required': True,
                'jurisdiction': tax_jurisdiction
            }

        # Calculate tax
        total_tax_rate = Decimal('0')
        applied_taxes = []

        for config in tax_configs:
            tax_rate = config.tax_rate
            tax_amount = amount * tax_rate

            applied_taxes.append({
                'tax_name': config.tax_name,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'jurisdiction': {
                    'country': config.country,
                    'state': config.state_province,
                    'city': config.city
                }
            })

            total_tax_rate += tax_rate

        total_tax_amount = amount * total_tax_rate

        logger.info(
            f"Calculated tax: ${total_tax_amount} ({total_tax_rate:.4%}) "
            f"on ${amount} for {tax_jurisdiction}"
        )

        return {
            'tax_amount': total_tax_amount,
            'tax_rate': total_tax_rate,
            'applied_taxes': applied_taxes,
            'nexus_required': True,
            'jurisdiction': tax_jurisdiction
        }

    def _determine_jurisdiction(
        self,
        origin_address: Dict,
        destination_address: Dict
    ) -> Dict:
        """
        Determine which jurisdiction's tax rules apply.

        Most US states use destination-based taxation.
        Some use origin-based.
        """
        dest_country = destination_address.get('country', 'US')
        dest_state = destination_address.get('state', '')

        # Origin-based states
        origin_based_states = ['CA', 'TX', 'AZ', 'OH', 'PA', 'MS', 'NM', 'UT', 'VA']

        if dest_country == 'US' and dest_state in origin_based_states:
            # Use origin address
            return origin_address
        else:
            # Use destination address (most common)
            return destination_address

    def _check_nexus(self, jurisdiction: Dict) -> bool:
        """
        Check if organization has nexus in the given jurisdiction.

        Nexus = legal requirement to collect tax in that jurisdiction.
        """
        country = jurisdiction.get('country', 'US')
        state = jurisdiction.get('state', '')

        # Check if we have any active tax configuration for this jurisdiction
        nexus_config = TaxConfiguration.objects.filter(
            organization=self.organization,
            country=country,
            state_province=state,
            has_nexus=True,
            is_active=True
        ).exists()

        return nexus_config

    def _get_applicable_taxes(
        self,
        jurisdiction: Dict,
        product_tax_code: str
    ) -> List[TaxConfiguration]:
        """
        Get all applicable tax configurations for a jurisdiction.

        Returns multiple configs (e.g., state + county + city tax).
        """
        country = jurisdiction.get('country', 'US')
        state = jurisdiction.get('state', '')
        city = jurisdiction.get('city', '')
        postal_code = jurisdiction.get('postal_code', '')

        # Query for matching tax configurations
        # Priority: Most specific (city) to least specific (state only)
        configs = TaxConfiguration.objects.filter(
            organization=self.organization,
            country=country,
            is_active=True,
            has_nexus=True
        ).filter(
            Q(state_province=state, city=city) |
            Q(state_province=state, city='') |
            Q(state_province=state, postal_code=postal_code)
        ).order_by('-city', '-postal_code')

        return list(configs)

    def create_nexus_configuration(
        self,
        country: str,
        state: str,
        tax_name: str,
        tax_rate: Decimal,
        tax_liability_account,
        effective_date=None
    ) -> TaxConfiguration:
        """
        Create a new nexus/tax configuration.

        Args:
            country: Country code (US, CA, etc.)
            state: State/province code
            tax_name: Name of tax (e.g., "California Sales Tax")
            tax_rate: Tax rate as decimal (0.0725 for 7.25%)
            tax_liability_account: GL account for tax payable
            effective_date: Date nexus became effective

        Returns:
            TaxConfiguration object
        """
        from django.utils import timezone

        config = TaxConfiguration.objects.create(
            organization=self.organization,
            country=country,
            state_province=state,
            tax_name=tax_name,
            tax_rate=tax_rate,
            tax_liability_account=tax_liability_account,
            has_nexus=True,
            nexus_date=effective_date or timezone.now().date(),
            applies_to_products=True,
            applies_to_shipping=False,
            is_active=True
        )

        logger.info(
            f"Created nexus configuration: {tax_name} "
            f"({state}, {country}) @ {tax_rate:.4%}"
        )

        return config
