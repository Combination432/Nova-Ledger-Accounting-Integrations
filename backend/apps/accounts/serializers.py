"""
Serializers for accounts app.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Organization, ChartOfAccounts, SalesChannel

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """User serializer with organization details."""

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'organization', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'password': {'write_only': True}}


class OrganizationSerializer(serializers.ModelSerializer):
    """Organization serializer."""
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            'id', 'name', 'tax_id', 'currency', 'fiscal_year_end',
            'accounting_method', 'subscription_tier', 'monthly_transaction_limit',
            'enable_inventory_tracking', 'enable_multi_currency', 'enable_landed_costs',
            'user_count', 'created_at', 'updated_at', 'is_active'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_user_count(self, obj):
        return obj.users.count()


class ChartOfAccountsSerializer(serializers.ModelSerializer):
    """Chart of Accounts serializer."""
    parent_account_name = serializers.CharField(source='parent_account.account_name', read_only=True)
    sub_accounts_count = serializers.SerializerMethodField()

    class Meta:
        model = ChartOfAccounts
        fields = [
            'id', 'organization', 'account_number', 'account_name',
            'account_type', 'account_subtype', 'description',
            'parent_account', 'parent_account_name', 'is_active',
            'is_sub_account', 'current_balance', 'quickbooks_id',
            'xero_id', 'netsuite_id', 'sub_accounts_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_sub_accounts_count(self, obj):
        return obj.sub_accounts.count()

    def validate(self, data):
        """Validate account data."""
        # Ensure parent account is not the same as the account itself
        if data.get('parent_account') == self.instance:
            raise serializers.ValidationError("Account cannot be its own parent")

        # If parent account is set, mark as sub-account
        if data.get('parent_account'):
            data['is_sub_account'] = True

        return data


class SalesChannelSerializer(serializers.ModelSerializer):
    """Sales channel serializer."""
    revenue_account_name = serializers.CharField(source='revenue_account.account_name', read_only=True)
    fee_account_name = serializers.CharField(source='fee_account.account_name', read_only=True)
    tax_account_name = serializers.CharField(source='tax_account.account_name', read_only=True)

    class Meta:
        model = SalesChannel
        fields = [
            'id', 'organization', 'name', 'channel_type',
            'revenue_account', 'revenue_account_name',
            'fee_account', 'fee_account_name',
            'tax_account', 'tax_account_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
