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
    quarterly_estimated_tax, tax_compliance_checklist,
    generate_journal_entry, batch_generate_journal_entries,
    import_historical_data, import_from_csv,
    batch_categorize, batch_operations,
    dashboard_kpis, build_custom_report, schedule_report
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
    # Export endpoints
    path('export/transactions/', export_transactions, name='export-transactions'),
    path('export/reconciliation/', export_reconciliation_report, name='export-reconciliation'),
    path('export/tax/', export_tax_report, name='export-tax'),
    path('export/forex/', export_forex_report, name='export-forex'),
    path('tax/summary/', tax_summary, name='tax-summary'),
    # OAuth endpoints
    path('oauth/initiate/', oauth_initiate, name='oauth-initiate'),
    path('oauth/callback/', oauth_callback, name='oauth-callback'),
    path('oauth/disconnect/', oauth_disconnect, name='oauth-disconnect'),
    path('oauth/refresh/', oauth_refresh, name='oauth-refresh'),
    # Webhook endpoints
    path('webhooks/shopify/', shopify_webhook, name='webhook-shopify'),
    path('webhooks/stripe/', stripe_webhook, name='webhook-stripe'),
    path('webhooks/quickbooks/', quickbooks_webhook, name='webhook-quickbooks'),
    path('webhooks/register/', register_webhooks, name='webhook-register'),
    # Tax endpoints
    path('tax/sales-tax/', sales_tax_summary, name='tax-sales-tax'),
    path('tax/vat/', vat_summary, name='tax-vat'),
    path('tax/1099/', form_1099_report, name='tax-1099'),
    path('tax/nexus/', nexus_analysis, name='tax-nexus'),
    path('tax/estimated/', quarterly_estimated_tax, name='tax-estimated'),
    path('tax/checklist/', tax_compliance_checklist, name='tax-checklist'),
    # Journal entry endpoints
    path('journal/generate/', generate_journal_entry, name='journal-generate'),
    path('journal/batch-generate/', batch_generate_journal_entries, name='journal-batch-generate'),
    # Historical import endpoints
    path('import/historical/', import_historical_data, name='import-historical'),
    path('import/csv/', import_from_csv, name='import-csv'),
    # Batch operations endpoints
    path('batch/categorize/', batch_categorize, name='batch-categorize'),
    path('batch/operations/', batch_operations, name='batch-operations'),
    # Analytics endpoints
    path('analytics/kpis/', dashboard_kpis, name='analytics-kpis'),
    path('analytics/custom-report/', build_custom_report, name='analytics-custom-report'),
    # Scheduled reports endpoints
    path('reports/schedule/', schedule_report, name='reports-schedule'),
]
