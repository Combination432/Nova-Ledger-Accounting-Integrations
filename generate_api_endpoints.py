#!/usr/bin/env python3
"""
Script to generate all missing API endpoints, serializers, and views for Nova Ledger.
Run this to complete FIX #1: Implement API Endpoints
"""

import os
from pathlib import Path

# Transaction serializers
TRANSACTION_SERIALIZERS = '''"""
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
'''

# Transaction views
TRANSACTION_VIEWS = '''"""
API views for transactions app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Transaction, JournalEntry, BankTransaction, BankAccount
from .serializers import (
    TransactionSerializer, JournalEntrySerializer,
    BankTransactionSerializer, BankAccountSerializer
)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source_platform', 'transaction_type', 'is_reconciled', 'sales_channel']
    search_fields = ['transaction_number', 'description', 'customer_name', 'customer_email']
    ordering_fields = ['transaction_date', 'gross_amount', 'created_at']
    ordering = ['-transaction_date']

    def get_queryset(self):
        return Transaction.objects.filter(
            organization=self.request.user.organization
        ).select_related('sales_channel', 'journal_entry').prefetch_related('fees', 'line_items')

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def reconcile(self, request, pk=None):
        """Mark transaction as reconciled."""
        transaction = self.get_object()
        bank_transaction_id = request.data.get('bank_transaction_id')

        from django.utils import timezone
        transaction.is_reconciled = True
        transaction.reconciliation_date = timezone.now()
        if bank_transaction_id:
            transaction.bank_transaction_id = bank_transaction_id
        transaction.save()

        return Response({'status': 'reconciled'})


class JournalEntryViewSet(viewsets.ModelViewSet):
    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'synced_to_accounting']
    search_fields = ['entry_number', 'description']
    ordering = ['-entry_date']

    def get_queryset(self):
        return JournalEntry.objects.filter(
            organization=self.request.user.organization
        ).prefetch_related('lines')

    @action(detail=True, methods=['post'])
    def post_entry(self, request, pk=None):
        """Post a journal entry."""
        entry = self.get_object()
        if not entry.is_balanced():
            return Response(
                {'error': 'Journal entry is not balanced'},
                status=status.HTTP_400_BAD_REQUEST
            )
        entry.status = 'posted'
        entry.save()
        return Response({'status': 'posted'})


class BankTransactionViewSet(viewsets.ModelViewSet):
    serializer_class = BankTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['bank_account', 'is_reconciled']
    ordering = ['-transaction_date']

    def get_queryset(self):
        return BankTransaction.objects.filter(
            organization=self.request.user.organization
        )


class BankAccountViewSet(viewsets.ModelViewSet):
    serializer_class = BankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'currency']

    def get_queryset(self):
        return BankAccount.objects.filter(
            organization=self.request.user.organization
        )
'''

# Transaction URLs
TRANSACTION_URLS = '''from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TransactionViewSet, JournalEntryViewSet,
    BankTransactionViewSet, BankAccountViewSet
)

router = DefaultRouter()
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'journal-entries', JournalEntryViewSet, basename='journalentry')
router.register(r'bank-transactions', BankTransactionViewSet, basename='banktransaction')
router.register(r'bank-accounts', BankAccountViewSet, basename='bankaccount')

urlpatterns = [
    path('', include(router.urls)),
]
'''

def write_file(path, content):
    """Write content to file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)
    print(f"✓ Created {path}")

# Write transaction files
BASE_DIR = Path(__file__).parent / 'backend' / 'apps' / 'transactions'
write_file(BASE_DIR / 'serializers.py', TRANSACTION_SERIALIZERS)
write_file(BASE_DIR / 'views.py', TRANSACTION_VIEWS)
write_file(BASE_DIR / 'urls.py', TRANSACTION_URLS)

print("\\n✅ Transaction API endpoints generated successfully!")
