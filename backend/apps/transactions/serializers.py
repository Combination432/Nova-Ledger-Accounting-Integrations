"""
Serializers for transactions app.
"""
from rest_framework import serializers
from decimal import Decimal
from .models import (
    Transaction, TransactionLineItem, Fee, JournalEntry,
    JournalEntryLine, BankTransaction, BankAccount, ReconciliationRule
)


class FeeSerializer(serializers.ModelSerializer):
    expense_account_name = serializers.CharField(source='expense_account.account_name', read_only=True)

    class Meta:
        model = Fee
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class TransactionLineItemSerializer(serializers.ModelSerializer):
    inventory_item_sku = serializers.CharField(source='inventory_item.sku', read_only=True, allow_null=True)

    class Meta:
        model = TransactionLineItem
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    fees = FeeSerializer(many=True, read_only=True)
    line_items = TransactionLineItemSerializer(many=True, read_only=True)
    total_fees = serializers.SerializerMethodField()
    total_cogs = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_fees(self, obj):
        return sum(fee.amount for fee in obj.fees.all())

    def get_total_cogs(self, obj):
        return sum(item.total_cogs or Decimal('0') for item in obj.line_items.all())


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.account_name', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    is_balanced = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_balanced(self, obj):
        return obj.is_balanced()


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = '__all__'


class BankTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = '__all__'


class ReconciliationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationRule
        fields = '__all__'
