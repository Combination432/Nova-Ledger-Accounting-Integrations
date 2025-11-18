"""
Serializers for integrations app.
"""
from rest_framework import serializers
from .models import (
    Integration, SyncLog, WebhookEndpoint, WebhookEvent, TaxConfiguration,
    TransactionRule, BankReconciliation, ReconciliationMatch,
    Currency, ExchangeRate, ForexGainLoss, AccountMapping, FieldMapping
)


class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Integration
        fields = '__all__'
        extra_kwargs = {
            'oauth_access_token': {'write_only': True},
            'oauth_refresh_token': {'write_only': True},
            'auth_credentials': {'write_only': True}
        }


class SyncLogSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source='integration.name', read_only=True)
    
    class Meta:
        model = SyncLog
        fields = '__all__'


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = '__all__'
        extra_kwargs = {'secret_key': {'write_only': True}}


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = '__all__'


class TaxConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxConfiguration
        fields = '__all__'


class TransactionRuleSerializer(serializers.ModelSerializer):
    target_account_name = serializers.CharField(source='target_account.account_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = TransactionRule
        fields = '__all__'
        read_only_fields = ['times_applied', 'last_applied_at', 'created_by']


class BankReconciliationSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(source='bank_account.account_name', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.get_full_name', read_only=True)

    class Meta:
        model = BankReconciliation
        fields = '__all__'
        read_only_fields = ['total_matched', 'total_unmatched', 'total_suggested', 'reconciled_at']


class ReconciliationMatchSerializer(serializers.ModelSerializer):
    bank_transaction_description = serializers.CharField(
        source='bank_transaction.description',
        read_only=True
    )
    bank_transaction_amount = serializers.DecimalField(
        source='bank_transaction.amount',
        max_digits=19,
        decimal_places=4,
        read_only=True
    )

    class Meta:
        model = ReconciliationMatch
        fields = '__all__'
        read_only_fields = ['confirmed_at']


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'


class ExchangeRateSerializer(serializers.ModelSerializer):
    from_currency_name = serializers.CharField(source='from_currency.name', read_only=True)
    to_currency_name = serializers.CharField(source='to_currency.name', read_only=True)

    class Meta:
        model = ExchangeRate
        fields = '__all__'


class ForexGainLossSerializer(serializers.ModelSerializer):
    from_currency_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_currency_code = serializers.CharField(source='to_currency.code', read_only=True)
    gl_account_name = serializers.CharField(source='gl_account.account_name', read_only=True)

    class Meta:
        model = ForexGainLoss
        fields = '__all__'


class AccountMappingSerializer(serializers.ModelSerializer):
    nova_account_name = serializers.CharField(source='nova_ledger_account.account_name', read_only=True)

    class Meta:
        model = AccountMapping
        fields = '__all__'


class FieldMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldMapping
        fields = '__all__'
