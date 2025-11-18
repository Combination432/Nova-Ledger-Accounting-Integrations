"""
Multi-currency support service with forex tracking.
Handles currency conversion and gain/loss calculation.
"""
from typing import Optional, Dict
from decimal import Decimal
from datetime import date, timedelta
from django.db.models import Q
from django.utils import timezone
from ..models import Currency, ExchangeRate, ForexGainLoss
from apps.transactions.models import Transaction
import logging
import requests

logger = logging.getLogger(__name__)


class CurrencyService:
    """
    Service for multi-currency operations and forex gain/loss tracking.
    """

    def __init__(self, organization):
        self.organization = organization
        self.base_currency = 'USD'  # Could be configurable per organization

    def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        conversion_date: Optional[date] = None
    ) -> Decimal:
        """
        Convert amount from one currency to another.

        Args:
            amount: Amount to convert
            from_currency: Source currency code (e.g., 'USD')
            to_currency: Target currency code (e.g., 'EUR')
            conversion_date: Date for conversion rate (defaults to today)

        Returns:
            Converted amount
        """
        if from_currency == to_currency:
            return amount

        if not conversion_date:
            conversion_date = timezone.now().date()

        # Get exchange rate
        rate = self.get_exchange_rate(from_currency, to_currency, conversion_date)

        if not rate:
            raise ValueError(
                f"No exchange rate found for {from_currency}/{to_currency} on {conversion_date}"
            )

        return amount * rate

    def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        Get exchange rate for a currency pair on a specific date.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for the rate

        Returns:
            Exchange rate or None if not found
        """
        # Try to get existing rate
        rate_obj = ExchangeRate.objects.filter(
            from_currency_id=from_currency,
            to_currency_id=to_currency,
            rate_date=rate_date
        ).first()

        if rate_obj:
            return rate_obj.rate

        # Try to get rate for previous days (up to 7 days back)
        for days_back in range(1, 8):
            previous_date = rate_date - timedelta(days=days_back)
            rate_obj = ExchangeRate.objects.filter(
                from_currency_id=from_currency,
                to_currency_id=to_currency,
                rate_date=previous_date
            ).first()

            if rate_obj:
                logger.info(
                    f"Using {days_back}-day-old rate for {from_currency}/{to_currency}"
                )
                return rate_obj.rate

        # Try to fetch from external API
        rate = self._fetch_external_rate(from_currency, to_currency, rate_date)
        if rate:
            # Save for future use
            self.save_exchange_rate(from_currency, to_currency, rate, rate_date, source='api')
            return rate

        return None

    def save_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        rate_date: date,
        source: str = 'manual'
    ) -> ExchangeRate:
        """
        Save an exchange rate.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate: Exchange rate
            rate_date: Date for the rate
            source: Source of the rate (manual, api, ecb, etc.)

        Returns:
            Created or updated ExchangeRate
        """
        # Ensure currencies exist
        from_curr, _ = Currency.objects.get_or_create(
            code=from_currency,
            defaults={'name': from_currency, 'symbol': from_currency}
        )
        to_curr, _ = Currency.objects.get_or_create(
            code=to_currency,
            defaults={'name': to_currency, 'symbol': to_currency}
        )

        # Create or update rate
        rate_obj, created = ExchangeRate.objects.update_or_create(
            from_currency=from_curr,
            to_currency=to_curr,
            rate_date=rate_date,
            defaults={'rate': rate, 'source': source}
        )

        # Also save inverse rate
        if rate > 0:
            inverse_rate = Decimal('1') / rate
            ExchangeRate.objects.update_or_create(
                from_currency=to_curr,
                to_currency=from_curr,
                rate_date=rate_date,
                defaults={'rate': inverse_rate, 'source': source}
            )

        logger.info(
            f"Saved exchange rate: {from_currency}/{to_currency} = {rate} ({rate_date}, {source})"
        )

        return rate_obj

    def _fetch_external_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        Fetch exchange rate from external API.

        Uses free API: https://exchangerate-api.com or ECB for EUR rates.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for the rate

        Returns:
            Exchange rate or None
        """
        try:
            # Try exchangerate-api.com (free tier)
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates', {})

                if to_currency in rates:
                    rate = Decimal(str(rates[to_currency]))
                    logger.info(f"Fetched rate from exchangerate-api.com: {from_currency}/{to_currency} = {rate}")
                    return rate

        except Exception as e:
            logger.warning(f"Failed to fetch rate from external API: {str(e)}")

        return None

    def calculate_forex_gain_loss(
        self,
        transaction: Transaction,
        revaluation_date: Optional[date] = None
    ) -> Optional[ForexGainLoss]:
        """
        Calculate forex gain/loss for a transaction.

        Args:
            transaction: Transaction to calculate gain/loss for
            revaluation_date: Date for revaluation (defaults to today)

        Returns:
            ForexGainLoss object or None if no forex impact
        """
        if not transaction.currency or transaction.currency == self.base_currency:
            return None  # No forex impact

        if not revaluation_date:
            revaluation_date = timezone.now().date()

        # Get original rate
        original_rate = self.get_exchange_rate(
            transaction.currency,
            self.base_currency,
            transaction.transaction_date
        )

        if not original_rate:
            logger.warning(
                f"No original rate for transaction {transaction.id} "
                f"({transaction.currency} on {transaction.transaction_date})"
            )
            return None

        # Get current rate
        current_rate = self.get_exchange_rate(
            transaction.currency,
            self.base_currency,
            revaluation_date
        )

        if not current_rate:
            logger.warning(
                f"No current rate for transaction {transaction.id} "
                f"({transaction.currency} on {revaluation_date})"
            )
            return None

        # Calculate amounts
        original_amount = transaction.gross_amount
        original_base_amount = original_amount * original_rate
        current_base_amount = original_amount * current_rate
        gain_loss_amount = current_base_amount - original_base_amount

        # Determine if realized or unrealized
        # For simplicity, consider it realized if transaction is settled/completed
        gain_loss_type = 'realized' if transaction.metadata.get('status') == 'completed' else 'unrealized'

        # Get or create forex gain/loss account
        from apps.accounts.models import ChartOfAccounts
        gl_account, _ = ChartOfAccounts.objects.get_or_create(
            organization=self.organization,
            account_type='revenue' if gain_loss_amount > 0 else 'expense',
            account_subtype='forex_gain' if gain_loss_amount > 0 else 'forex_loss',
            defaults={
                'account_number': '7000' if gain_loss_amount > 0 else '8000',
                'account_name': 'Forex Gains' if gain_loss_amount > 0 else 'Forex Losses'
            }
        )

        # Create forex gain/loss record
        forex_gl = ForexGainLoss.objects.create(
            organization=self.organization,
            transaction=transaction,
            from_currency_id=transaction.currency,
            to_currency_id=self.base_currency,
            original_amount=original_amount,
            converted_amount=current_base_amount,
            gain_loss_amount=gain_loss_amount,
            original_rate=original_rate,
            current_rate=current_rate,
            gain_loss_type=gain_loss_type,
            gl_account=gl_account,
            calculation_date=revaluation_date
        )

        logger.info(
            f"Calculated {gain_loss_type} forex {('gain' if gain_loss_amount > 0 else 'loss')} "
            f"of {abs(gain_loss_amount)} {self.base_currency} for transaction {transaction.id}"
        )

        return forex_gl

    def revalue_open_transactions(self, revaluation_date: Optional[date] = None) -> Dict:
        """
        Revalue all open foreign currency transactions.

        Args:
            revaluation_date: Date for revaluation (defaults to today)

        Returns:
            Dict with revaluation summary
        """
        if not revaluation_date:
            revaluation_date = timezone.now().date()

        # Get open foreign currency transactions
        open_transactions = Transaction.objects.filter(
            organization=self.organization,
        ).exclude(
            Q(currency__isnull=True) | Q(currency=self.base_currency)
        ).filter(
            # Add logic here to determine "open" transactions
            # For example: not yet reconciled, not fully paid, etc.
            metadata__status__in=['pending', 'authorized']
        )

        total_gain = Decimal('0')
        total_loss = Decimal('0')
        count = 0

        for transaction in open_transactions:
            forex_gl = self.calculate_forex_gain_loss(transaction, revaluation_date)
            if forex_gl:
                if forex_gl.gain_loss_amount > 0:
                    total_gain += forex_gl.gain_loss_amount
                else:
                    total_loss += abs(forex_gl.gain_loss_amount)
                count += 1

        logger.info(
            f"Revalued {count} transactions: "
            f"+{total_gain} {self.base_currency} gains, "
            f"-{total_loss} {self.base_currency} losses"
        )

        return {
            'revaluation_date': revaluation_date.isoformat(),
            'transactions_revalued': count,
            'total_gains': float(total_gain),
            'total_losses': float(total_loss),
            'net_gain_loss': float(total_gain - total_loss),
            'base_currency': self.base_currency
        }

    def load_common_currencies(self):
        """
        Load common currencies into the database.
        """
        common_currencies = [
            {'code': 'USD', 'name': 'US Dollar', 'symbol': '$'},
            {'code': 'EUR', 'name': 'Euro', 'symbol': '€'},
            {'code': 'GBP', 'name': 'British Pound', 'symbol': '£'},
            {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'decimal_places': 0},
            {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'CA$'},
            {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$'},
            {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF'},
            {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥'},
            {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹'},
            {'code': 'MXN', 'name': 'Mexican Peso', 'symbol': 'MX$'},
        ]

        created_count = 0
        for currency_data in common_currencies:
            _, created = Currency.objects.get_or_create(
                code=currency_data['code'],
                defaults=currency_data
            )
            if created:
                created_count += 1

        logger.info(f"Loaded {created_count} new currencies")
        return created_count
