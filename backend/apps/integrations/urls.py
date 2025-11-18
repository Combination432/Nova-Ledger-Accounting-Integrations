from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    IntegrationViewSet, SyncLogViewSet,
    WebhookEventViewSet, TaxConfigurationViewSet,
    TransactionRuleViewSet, BankReconciliationViewSet,
    ReconciliationMatchViewSet, CurrencyViewSet,
    ExchangeRateViewSet, ForexGainLossViewSet
)

router = DefaultRouter()
router.register(r'', IntegrationViewSet, basename='integration')
router.register(r'sync-logs', SyncLogViewSet, basename='synclog')
router.register(r'webhook-events', WebhookEventViewSet, basename='webhookevent')
router.register(r'tax-config', TaxConfigurationViewSet, basename='taxconfiguration')
router.register(r'rules', TransactionRuleViewSet, basename='transactionrule')
router.register(r'reconciliations', BankReconciliationViewSet, basename='reconciliation')
router.register(r'reconciliation-matches', ReconciliationMatchViewSet, basename='reconciliationmatch')
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'exchange-rates', ExchangeRateViewSet, basename='exchangerate')
router.register(r'forex-gains-losses', ForexGainLossViewSet, basename='forexgainloss')

urlpatterns = [
    path('', include(router.urls)),
]
