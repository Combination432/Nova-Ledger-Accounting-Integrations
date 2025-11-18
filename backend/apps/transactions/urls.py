from django.urls import path, include
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
