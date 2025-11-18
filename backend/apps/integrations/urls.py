from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    IntegrationViewSet, SyncLogViewSet,
    WebhookEventViewSet, TaxConfigurationViewSet,
    TransactionRuleViewSet, BankReconciliationViewSet,
    ReconciliationMatchViewSet, CurrencyViewSet,
    ExchangeRateViewSet, ForexGainLossViewSet,
    export_transactions, export_reconciliation_report,
    export_tax_report, export_forex_report, tax_summary,
    oauth_initiate, oauth_callback, oauth_disconnect, oauth_refresh,
    shopify_webhook, stripe_webhook, quickbooks_webhook, register_webhooks,
    sales_tax_summary, vat_summary, form_1099_report, nexus_analysis,
    quarterly_estimated_tax, tax_compliance_checklist
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
    path('export/transactions/', export_transactions, name='export-transactions'),
    path('export/reconciliation/', export_reconciliation_report, name='export-reconciliation'),
    path('export/tax/', export_tax_report, name='export-tax'),
    path('export/forex/', export_forex_report, name='export-forex'),
    path('tax/summary/', tax_summary, name='tax-summary'),
    path('oauth/initiate/', oauth_initiate, name='oauth-initiate'),
    path('oauth/callback/', oauth_callback, name='oauth-callback'),
    path('oauth/disconnect/', oauth_disconnect, name='oauth-disconnect'),
    path('oauth/refresh/', oauth_refresh, name='oauth-refresh'),
    path('webhooks/shopify/', shopify_webhook, name='webhook-shopify'),
    path('webhooks/stripe/', stripe_webhook, name='webhook-stripe'),
    path('webhooks/quickbooks/', quickbooks_webhook, name='webhook-quickbooks'),
    path('webhooks/register/', register_webhooks, name='webhook-register'),
    path('tax/sales-tax/', sales_tax_summary, name='tax-sales-tax'),
    path('tax/vat/', vat_summary, name='tax-vat'),
    path('tax/1099/', form_1099_report, name='tax-1099'),
    path('tax/nexus/', nexus_analysis, name='tax-nexus'),
    path('tax/estimated/', quarterly_estimated_tax, name='tax-estimated'),
    path('tax/checklist/', tax_compliance_checklist, name='tax-checklist'),
]
