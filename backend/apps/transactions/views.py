"""
API views for transactions app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.common.permissions import CanManageFinancials, BelongsToOrganization
from .models import Transaction, JournalEntry, BankTransaction, BankAccount
from .serializers import (
    TransactionSerializer, JournalEntrySerializer,
    BankTransactionSerializer, BankAccountSerializer
)


class TransactionViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageFinancials, BelongsToOrganization]
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
    permission_classes = [permissions.IsAuthenticated, CanManageFinancials, BelongsToOrganization]
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
    permission_classes = [permissions.IsAuthenticated, CanManageFinancials, BelongsToOrganization]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['bank_account', 'is_reconciled']
    ordering = ['-transaction_date']

    def get_queryset(self):
        return BankTransaction.objects.filter(
            organization=self.request.user.organization
        )


class BankAccountViewSet(viewsets.ModelViewSet):
    serializer_class = BankAccountSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageFinancials, BelongsToOrganization]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'currency']

    def get_queryset(self):
        return BankAccount.objects.filter(
            organization=self.request.user.organization
        )
