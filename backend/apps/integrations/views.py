"""
API views for integrations app.
"""
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime
from django.utils import timezone
from .models import (
    Integration, SyncLog, WebhookEvent, TaxConfiguration,
    TransactionRule, BankReconciliation, ReconciliationMatch,
    Currency, ExchangeRate, ForexGainLoss
)
from .serializers import (
    IntegrationSerializer, SyncLogSerializer,
    WebhookEventSerializer, TaxConfigurationSerializer,
    TransactionRuleSerializer, BankReconciliationSerializer,
    ReconciliationMatchSerializer, CurrencySerializer,
    ExchangeRateSerializer, ForexGainLossSerializer
)


class IntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = IntegrationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['integration_type', 'is_active', 'is_connected']
    search_fields = ['name', 'integration_type']

    def get_queryset(self):
        return Integration.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def sync(self, request, pk=None):
        """
        Trigger manual sync for this integration.

        Query params:
        - force_full_sync: (bool) If true, perform full sync instead of incremental
        - async: (bool) If true, queue sync task and return immediately (default: false)
        """
        integration = self.get_object()
        force_full_sync = request.data.get('force_full_sync', False)
        async_sync = request.data.get('async', False)

        if not integration.is_active:
            return Response(
                {'error': 'Integration is not active'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if async_sync:
                # Queue the sync task
                from .tasks import sync_integration_transactions
                task = sync_integration_transactions.delay(str(integration.id), force_full_sync)

                return Response({
                    'status': 'queued',
                    'task_id': task.id,
                    'message': 'Sync task queued successfully'
                }, status=status.HTTP_202_ACCEPTED)
            else:
                # Run sync synchronously
                from .sync_engine import SyncEngine
                engine = SyncEngine(integration)
                result = engine.sync_transactions(force_full_sync=force_full_sync)

                return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sync_status(self, request, pk=None):
        """
        Get current sync status for this integration.
        Returns information about last sync, next scheduled sync, and statistics.
        """
        integration = self.get_object()

        try:
            from .sync_engine import SyncEngine
            engine = SyncEngine(integration)
            status_info = engine.get_sync_status()

            return Response(status_info, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sync_logs(self, request, pk=None):
        """Get sync logs for this integration."""
        integration = self.get_object()
        logs = integration.sync_logs.order_by('-started_at')[:50]
        return Response(SyncLogSerializer(logs, many=True).data)


class SyncLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SyncLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'sync_type', 'integration']
    ordering = ['-started_at']

    def get_queryset(self):
        return SyncLog.objects.filter(
            integration__organization=self.request.user.organization
        )


class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WebhookEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'event_type']
    ordering = ['-received_at']

    def get_queryset(self):
        return WebhookEvent.objects.filter(
            webhook_endpoint__integration__organization=self.request.user.organization
        )


class TaxConfigurationViewSet(viewsets.ModelViewSet):
    serializer_class = TaxConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['country', 'state_province', 'is_active', 'has_nexus']
    search_fields = ['tax_name', 'country', 'state_province']

    def get_queryset(self):
        return TaxConfiguration.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class TransactionRuleViewSet(viewsets.ModelViewSet):
    serializer_class = TransactionRuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['rule_type', 'action', 'is_active', 'auto_apply']
    search_fields = ['name', 'description']
    ordering_fields = ['priority', 'created_at', 'times_applied']
    ordering = ['priority']

    def get_queryset(self):
        return TransactionRule.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def test_rule(self, request, pk=None):
        """Test a rule against sample transactions."""
        rule = self.get_object()
        transaction_ids = request.data.get('transaction_ids', [])

        from apps.transactions.models import Transaction
        from .services import AutoCategorizationService

        transactions = Transaction.objects.filter(
            id__in=transaction_ids,
            organization=self.request.user.organization
        )

        service = AutoCategorizationService(self.request.user.organization)
        results = []

        for txn in transactions:
            if service._rule_matches(rule, txn):
                results.append({
                    'transaction_id': str(txn.id),
                    'matches': True,
                    'description': txn.description,
                    'amount': str(txn.gross_amount)
                })
            else:
                results.append({
                    'transaction_id': str(txn.id),
                    'matches': False
                })

        return Response({
            'rule_id': str(rule.id),
            'tested_transactions': len(results),
            'matches': sum(1 for r in results if r['matches']),
            'results': results
        })

    @action(detail=False, methods=['post'])
    def apply_to_batch(self, request):
        """Apply rules to a batch of transactions."""
        transaction_ids = request.data.get('transaction_ids', [])

        from apps.transactions.models import Transaction
        from .services import AutoCategorizationService

        transactions = Transaction.objects.filter(
            id__in=transaction_ids,
            organization=self.request.user.organization
        )

        service = AutoCategorizationService(self.request.user.organization)
        result = service.categorize_batch(list(transactions))

        return Response(result)


class BankReconciliationViewSet(viewsets.ModelViewSet):
    serializer_class = BankReconciliationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'bank_account']
    ordering = ['-period_end']

    def get_queryset(self):
        return BankReconciliation.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['post'])
    def auto_match(self, request, pk=None):
        """Run automatic matching for this reconciliation."""
        reconciliation = self.get_object()
        confidence_threshold = float(request.data.get('confidence_threshold', 80.0))

        from .services import ReconciliationService

        service = ReconciliationService(reconciliation)
        result = service.auto_match(confidence_threshold=confidence_threshold)

        return Response(result)

    @action(detail=True, methods=['post'])
    def manual_match(self, request, pk=None):
        """Create a manual match."""
        reconciliation = self.get_object()
        bank_transaction_id = request.data.get('bank_transaction_id')
        transaction_ids = request.data.get('transaction_ids', [])
        notes = request.data.get('notes', '')

        from .services import ReconciliationService

        service = ReconciliationService(reconciliation)
        match = service.manual_match(bank_transaction_id, transaction_ids, notes)

        return Response(ReconciliationMatchSerializer(match).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete the reconciliation."""
        reconciliation = self.get_object()

        from .services import ReconciliationService

        service = ReconciliationService(reconciliation)
        success = service.complete_reconciliation(request.user)

        return Response({
            'success': success,
            'status': reconciliation.status,
            'reconciled_at': reconciliation.reconciled_at
        })

    @action(detail=True, methods=['get'])
    def unmatched(self, request, pk=None):
        """Get unmatched transactions for this reconciliation."""
        reconciliation = self.get_object()

        from .services import ReconciliationService

        service = ReconciliationService(reconciliation)
        unmatched = service.get_unmatched_transactions()

        return Response(unmatched)


class ReconciliationMatchViewSet(viewsets.ModelViewSet):
    serializer_class = ReconciliationMatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['reconciliation', 'match_type', 'is_confirmed']
    ordering = ['-created_at']

    def get_queryset(self):
        return ReconciliationMatch.objects.filter(
            reconciliation__organization=self.request.user.organization
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a suggested match."""
        from django.utils import timezone
        match = self.get_object()
        match.is_confirmed = True
        match.confirmed_by = request.user
        match.confirmed_at = timezone.now()
        match.save()

        return Response(ReconciliationMatchSerializer(match).data)

    @action(detail=True, methods=['delete'])
    def unmatch(self, request, pk=None):
        """Remove a match."""
        match = self.get_object()
        reconciliation = match.reconciliation

        from .services import ReconciliationService

        service = ReconciliationService(reconciliation)
        success = service.unmatch(str(match.id))

        return Response({'success': success}, status=status.HTTP_204_NO_CONTENT if success else status.HTTP_400_BAD_REQUEST)


class CurrencyViewSet(viewsets.ModelViewSet):
    serializer_class = CurrencySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    ordering = ['code']
    queryset = Currency.objects.all()

    @action(detail=False, methods=['post'])
    def load_common(self, request):
        """Load common currencies."""
        from .services import CurrencyService

        service = CurrencyService(request.user.organization)
        count = service.load_common_currencies()

        return Response({'currencies_loaded': count})


class ExchangeRateViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRateSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['from_currency', 'to_currency', 'rate_date', 'source']
    ordering = ['-rate_date']
    queryset = ExchangeRate.objects.all()

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """Convert an amount between currencies."""
        from decimal import Decimal
        from datetime import datetime
        from django.utils import timezone
        from .services import CurrencyService

        amount = Decimal(str(request.data.get('amount')))
        from_currency = request.data.get('from_currency')
        to_currency = request.data.get('to_currency')
        conversion_date = request.data.get('conversion_date')

        if conversion_date:
            conversion_date = datetime.fromisoformat(conversion_date).date()

        service = CurrencyService(request.user.organization)
        converted_amount = service.convert_amount(
            amount, from_currency, to_currency, conversion_date
        )

        rate = service.get_exchange_rate(from_currency, to_currency, conversion_date or timezone.now().date())

        return Response({
            'amount': str(amount),
            'from_currency': from_currency,
            'to_currency': to_currency,
            'converted_amount': str(converted_amount),
            'exchange_rate': str(rate),
            'conversion_date': (conversion_date or timezone.now().date()).isoformat()
        })

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """Bulk import exchange rates."""
        from decimal import Decimal
        from datetime import datetime
        from .services import CurrencyService

        rates = request.data.get('rates', [])
        service = CurrencyService(request.user.organization)

        imported = 0
        for rate_data in rates:
            service.save_exchange_rate(
                from_currency=rate_data['from_currency'],
                to_currency=rate_data['to_currency'],
                rate=Decimal(str(rate_data['rate'])),
                rate_date=datetime.fromisoformat(rate_data['rate_date']).date(),
                source=rate_data.get('source', 'manual')
            )
            imported += 1

        return Response({'imported': imported})


class ForexGainLossViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ForexGainLossSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['gain_loss_type', 'from_currency', 'to_currency']
    ordering = ['-calculation_date']

    def get_queryset(self):
        return ForexGainLoss.objects.filter(
            organization=self.request.user.organization
        )

    @action(detail=False, methods=['post'])
    def revalue(self, request):
        """Revalue all open foreign currency transactions."""
        from datetime import datetime
        from .services import CurrencyService

        revaluation_date = request.data.get('revaluation_date')
        if revaluation_date:
            revaluation_date = datetime.fromisoformat(revaluation_date).date()

        service = CurrencyService(request.user.organization)
        result = service.revalue_open_transactions(revaluation_date)

        return Response(result)


# ============================================================================
# Export and Reporting Endpoints
# ============================================================================

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def export_transactions(request):
    """
    Export transactions to CSV or Excel.

    POST body:
    {
        "format": "csv" | "excel",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "platform": "shopify" (optional)
    }
    """
    from apps.transactions.models import Transaction
    from .services import ExportService

    format_type = request.data.get('format', 'csv')
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')
    platform = request.data.get('platform')

    # Build query
    transactions = Transaction.objects.filter(
        organization=request.user.organization
    )

    if start_date:
        transactions = transactions.filter(transaction_date__gte=datetime.fromisoformat(start_date).date())
    if end_date:
        transactions = transactions.filter(transaction_date__lte=datetime.fromisoformat(end_date).date())
    if platform:
        transactions = transactions.filter(source_platform=platform)

    transactions = transactions.order_by('transaction_date')

    # Export
    service = ExportService(request.user.organization)

    if format_type == 'excel':
        buffer, filename = service.export_transactions_excel(transactions)
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        buffer, filename = service.export_transactions_csv(transactions)
        content_type = 'text/csv'

    response = HttpResponse(buffer.getvalue(), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def export_reconciliation_report(request):
    """
    Export reconciliation report to Excel.

    POST body:
    {
        "reconciliation_id": "uuid"
    }
    """
    from .services import ExportService

    reconciliation_id = request.data.get('reconciliation_id')

    reconciliation = BankReconciliation.objects.get(
        id=reconciliation_id,
        organization=request.user.organization
    )

    service = ExportService(request.user.organization)
    buffer, filename = service.export_reconciliation_report_excel(reconciliation)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def export_tax_report(request):
    """
    Export tax report to Excel.

    POST body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }
    """
    from .services import ExportService

    start_date = datetime.fromisoformat(request.data.get('start_date')).date()
    end_date = datetime.fromisoformat(request.data.get('end_date')).date()

    service = ExportService(request.user.organization)
    buffer, filename = service.export_tax_report_excel(start_date, end_date)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def export_forex_report(request):
    """
    Export forex gains/losses report to Excel.

    POST body:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }
    """
    from .services import ExportService

    start_date = datetime.fromisoformat(request.data.get('start_date')).date()
    end_date = datetime.fromisoformat(request.data.get('end_date')).date()

    service = ExportService(request.user.organization)
    buffer, filename = service.export_forex_report_excel(start_date, end_date)

    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def tax_summary(request):
    """
    Get tax summary for a date range.

    Query params:
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """
    from apps.transactions.models import Transaction
    from decimal import Decimal

    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    if not start_date or not end_date:
        return Response(
            {'error': 'start_date and end_date are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    start_date = datetime.fromisoformat(start_date).date()
    end_date = datetime.fromisoformat(end_date).date()

    # Get tax configurations
    tax_configs = TaxConfiguration.objects.filter(
        organization=request.user.organization,
        is_active=True
    )

    # Get transactions in date range
    transactions = Transaction.objects.filter(
        organization=request.user.organization,
        transaction_date__gte=start_date,
        transaction_date__lte=end_date
    )

    summary = []
    for tax_config in tax_configs:
        # Calculate total for this tax jurisdiction
        # In production, you'd have more sophisticated tax calculation
        taxable_amount = sum(
            txn.gross_amount for txn in transactions
            if txn.currency == 'USD'  # Simplified
        )

        tax_amount = taxable_amount * tax_config.tax_rate

        summary.append({
            'tax_name': tax_config.tax_name,
            'tax_rate': float(tax_config.tax_rate),
            'country': tax_config.country,
            'state_province': tax_config.state_province,
            'taxable_amount': float(taxable_amount),
            'tax_collected': float(tax_amount),
            'has_nexus': tax_config.has_nexus
        })

    return Response({
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'tax_jurisdictions': summary,
        'total_tax_collected': sum(item['tax_collected'] for item in summary)
    })


# OAuth endpoints

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def oauth_initiate(request):
    """
    Initiate OAuth authorization flow.
    
    Query params:
    - platform: Integration platform (shopify, stripe, quickbooks)
    - shop: Shopify shop name (required for Shopify)
    - integration_id: Optional existing integration ID to update
    
    Returns redirect URL for user to authorize
    """
    from .services.oauth_service import OAuthService
    from django.contrib.sites.shortcuts import get_current_site
    
    platform = request.GET.get('platform')
    shop = request.GET.get('shop')
    integration_id = request.GET.get('integration_id')
    
    if not platform:
        return Response(
            {'error': 'platform parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        oauth_service = OAuthService(platform, request.user.organization)
        
        # Build redirect URI
        current_site = get_current_site(request)
        protocol = 'https' if request.is_secure() else 'http'
        redirect_uri = f"{protocol}://{current_site.domain}/api/integrations/oauth/callback/"
        
        # Generate authorization URL
        auth_url, state, code_verifier = oauth_service.generate_authorization_url(
            redirect_uri=redirect_uri,
            shop=shop
        )
        
        # Store state and code_verifier in session for validation
        request.session[f'oauth_state_{platform}'] = state
        request.session[f'oauth_platform'] = platform
        
        if integration_id:
            request.session[f'oauth_integration_id'] = integration_id
        
        if code_verifier:
            request.session[f'oauth_code_verifier_{platform}'] = code_verifier
        
        if shop:
            request.session[f'oauth_shop_{platform}'] = shop
        
        return Response({
            'authorization_url': auth_url,
            'state': state,
            'platform': platform
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def oauth_callback(request):
    """
    OAuth callback endpoint.
    
    Query params:
    - code: Authorization code from OAuth provider
    - state: CSRF protection state token
    - shop: Shopify shop name (for Shopify)
    - realmId: QuickBooks company ID (for QuickBooks)
    
    Creates or updates integration with OAuth tokens
    """
    from .services.oauth_service import OAuthService
    from django.contrib.sites.shortcuts import get_current_site
    from datetime import timedelta
    
    code = request.GET.get('code')
    state = request.GET.get('state')
    shop = request.GET.get('shop')
    realm_id = request.GET.get('realmId')  # QuickBooks
    error = request.GET.get('error')
    
    # Check for OAuth errors
    if error:
        error_description = request.GET.get('error_description', 'Unknown error')
        return Response(
            {'error': error, 'description': error_description},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not code or not state:
        return Response(
            {'error': 'Missing code or state parameter'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get platform from session
    platform = request.session.get('oauth_platform')
    if not platform:
        return Response(
            {'error': 'OAuth session expired or invalid'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate state (CSRF protection)
    stored_state = request.session.get(f'oauth_state_{platform}')
    if not stored_state or stored_state != state:
        return Response(
            {'error': 'Invalid state parameter - possible CSRF attack'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        oauth_service = OAuthService(platform, request.user.organization)
        
        # Get stored values from session
        code_verifier = request.session.get(f'oauth_code_verifier_{platform}')
        stored_shop = request.session.get(f'oauth_shop_{platform}')
        integration_id = request.session.get('oauth_integration_id')
        
        # Use shop from callback or session
        shop = shop or stored_shop
        
        # Build redirect URI
        current_site = get_current_site(request)
        protocol = 'https' if request.is_secure() else 'http'
        redirect_uri = f"{protocol}://{current_site.domain}/api/integrations/oauth/callback/"
        
        # Exchange code for token
        token_data = oauth_service.exchange_code_for_token(
            code=code,
            redirect_uri=redirect_uri,
            shop=shop,
            code_verifier=code_verifier,
            realm_id=realm_id
        )
        
        # Create or update integration
        if integration_id:
            integration = Integration.objects.get(
                id=integration_id,
                organization=request.user.organization
            )
        else:
            # Create new integration
            integration = Integration.objects.create(
                organization=request.user.organization,
                integration_type=platform,
                name=f"{platform.title()} Integration",
                is_active=True
            )
        
        # Store OAuth tokens
        integration.oauth_access_token = token_data['access_token']
        integration.oauth_refresh_token = token_data.get('refresh_token', '')
        
        if token_data.get('expires_in'):
            integration.oauth_token_expiry = timezone.now() + timedelta(seconds=token_data['expires_in'])
        
        # Store platform-specific data
        credentials = integration.auth_credentials or {}
        
        if platform == 'shopify' and shop:
            credentials['shop'] = shop
            integration.name = f"Shopify - {shop}"
        elif platform == 'stripe':
            credentials['stripe_user_id'] = token_data.get('stripe_user_id')
            credentials['stripe_publishable_key'] = token_data.get('stripe_publishable_key')
        elif platform == 'quickbooks' and realm_id:
            credentials['realm_id'] = realm_id
        
        integration.auth_credentials = credentials
        integration.is_connected = True
        integration.connection_status = 'connected'
        integration.last_successful_sync = timezone.now()
        
        integration.save()
        
        # Clean up session
        request.session.pop(f'oauth_state_{platform}', None)
        request.session.pop(f'oauth_code_verifier_{platform}', None)
        request.session.pop(f'oauth_shop_{platform}', None)
        request.session.pop('oauth_platform', None)
        request.session.pop('oauth_integration_id', None)
        
        return Response({
            'success': True,
            'integration_id': str(integration.id),
            'platform': platform,
            'message': f'Successfully connected {platform.title()} integration'
        })
        
    except Integration.DoesNotExist:
        return Response(
            {'error': 'Integration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'OAuth callback failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def oauth_disconnect(request):
    """
    Disconnect and revoke OAuth integration.
    
    Body params:
    - integration_id: Integration ID to disconnect
    """
    from .services.oauth_service import OAuthService
    
    integration_id = request.data.get('integration_id')
    
    if not integration_id:
        return Response(
            {'error': 'integration_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        integration = Integration.objects.get(
            id=integration_id,
            organization=request.user.organization
        )
        
        oauth_service = OAuthService(integration.integration_type, request.user.organization)
        success = oauth_service.revoke_token(integration)
        
        if success:
            return Response({
                'success': True,
                'message': f'{integration.integration_type.title()} integration disconnected successfully'
            })
        else:
            return Response(
                {'error': 'Failed to revoke token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except Integration.DoesNotExist:
        return Response(
            {'error': 'Integration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Disconnect failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def oauth_refresh(request):
    """
    Manually refresh OAuth token.
    
    Body params:
    - integration_id: Integration ID to refresh
    """
    from .services.oauth_service import OAuthService
    
    integration_id = request.data.get('integration_id')
    
    if not integration_id:
        return Response(
            {'error': 'integration_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        integration = Integration.objects.get(
            id=integration_id,
            organization=request.user.organization
        )
        
        oauth_service = OAuthService(integration.integration_type, request.user.organization)
        token_data = oauth_service.refresh_access_token(integration)
        
        return Response({
            'success': True,
            'message': 'Token refreshed successfully',
            'expires_in': token_data.get('expires_in'),
            'token_expiry': integration.oauth_token_expiry.isoformat() if integration.oauth_token_expiry else None
        })
        
    except Integration.DoesNotExist:
        return Response(
            {'error': 'Integration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Token refresh failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Webhook handler endpoints

@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Public endpoint
def shopify_webhook(request):
    """
    Handle incoming Shopify webhooks.
    
    Headers:
    - X-Shopify-Hmac-SHA256: Webhook signature
    - X-Shopify-Shop-Domain: Shop domain
    - X-Shopify-Topic: Event topic
    """
    from .services.webhook_service import WebhookService
    import json
    
    # Get headers
    signature = request.META.get('HTTP_X_SHOPIFY_HMAC_SHA256')
    shop_domain = request.META.get('HTTP_X_SHOPIFY_SHOP_DOMAIN')
    event_type = request.META.get('HTTP_X_SHOPIFY_TOPIC')
    
    if not signature or not shop_domain or not event_type:
        return Response(
            {'error': 'Missing required headers'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Find integration by shop domain
    try:
        integration = Integration.objects.get(
            integration_type='shopify',
            auth_credentials__shop__icontains=shop_domain.replace('.myshopify.com', ''),
            is_active=True
        )
    except Integration.DoesNotExist:
        return Response(
            {'error': 'Integration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get webhook secret
    webhook_secret = integration.settings.get('webhook_secret', '')
    
    if not webhook_secret:
        logger.warning(f"No webhook secret configured for integration {integration.id}")
        # Continue anyway for development
    
    # Verify signature
    webhook_service = WebhookService('shopify')
    payload = request.body
    
    if webhook_secret:
        is_valid = webhook_service.verify_signature(
            payload=payload,
            signature=signature,
            secret=webhook_secret
        )
        
        if not is_valid:
            logger.error(f"Invalid Shopify webhook signature from {shop_domain}")
            return Response(
                {'error': 'Invalid signature'},
                status=status.HTTP_401_UNAUTHORIZED
            )
    
    # Process webhook
    try:
        payload_data = json.loads(payload.decode('utf-8'))
        event_id = payload_data.get('id', '')
        
        webhook_event = webhook_service.process_webhook(
            integration=integration,
            event_type=event_type,
            payload=payload_data,
            event_id=str(event_id)
        )
        
        return Response({'status': 'received', 'event_id': str(webhook_event.id)})
        
    except Exception as e:
        logger.error(f"Failed to process Shopify webhook: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Public endpoint
def stripe_webhook(request):
    """
    Handle incoming Stripe webhooks.
    
    Headers:
    - Stripe-Signature: Webhook signature with timestamp
    """
    from .services.webhook_service import WebhookService
    import json
    
    signature = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not signature:
        return Response(
            {'error': 'Missing Stripe-Signature header'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    payload = request.body
    
    try:
        payload_data = json.loads(payload.decode('utf-8'))
        event_type = payload_data.get('type')
        event_id = payload_data.get('id')
        
        # Get account ID from payload
        account_id = payload_data.get('account')
        
        if not account_id:
            # For direct integrations (not Connect)
            # Try to find by organization
            logger.warning("No account ID in Stripe webhook, using first active integration")
            integration = Integration.objects.filter(
                integration_type='stripe',
                is_active=True
            ).first()
        else:
            # Find integration by Stripe account ID
            integration = Integration.objects.filter(
                integration_type='stripe',
                auth_credentials__stripe_user_id=account_id,
                is_active=True
            ).first()
        
        if not integration:
            return Response(
                {'error': 'Integration not found for this account'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get webhook secret (endpoint secret from Stripe)
        webhook_secret = integration.settings.get('webhook_secret', '')
        
        # Verify signature
        webhook_service = WebhookService('stripe')
        
        if webhook_secret:
            is_valid = webhook_service.verify_signature(
                payload=payload,
                signature=signature,
                secret=webhook_secret,
                headers=request.META
            )
            
            if not is_valid:
                logger.error(f"Invalid Stripe webhook signature for integration {integration.id}")
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        # Process webhook
        webhook_event = webhook_service.process_webhook(
            integration=integration,
            event_type=event_type,
            payload=payload_data,
            event_id=event_id
        )
        
        return Response({'status': 'received', 'event_id': str(webhook_event.id)})
        
    except Exception as e:
        logger.error(f"Failed to process Stripe webhook: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Public endpoint
def quickbooks_webhook(request):
    """
    Handle incoming QuickBooks webhooks.
    
    Headers:
    - intuit-signature: Webhook signature
    """
    from .services.webhook_service import WebhookService
    import json
    
    signature = request.META.get('HTTP_INTUIT_SIGNATURE')
    
    if not signature:
        return Response(
            {'error': 'Missing intuit-signature header'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    payload = request.body
    
    try:
        payload_data = json.loads(payload.decode('utf-8'))
        
        # QuickBooks sends batch of notifications
        notifications = payload_data.get('eventNotifications', [])
        
        if not notifications:
            return Response({'status': 'no_events'})
        
        # Get realm ID from first notification
        realm_id = notifications[0].get('realmId')
        
        # Find integration by realm ID
        integration = Integration.objects.filter(
            integration_type='quickbooks',
            auth_credentials__realm_id=realm_id,
            is_active=True
        ).first()
        
        if not integration:
            return Response(
                {'error': 'Integration not found for this realm'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get webhook secret (verifier token)
        webhook_secret = integration.settings.get('webhook_secret', '')
        
        # Verify signature
        webhook_service = WebhookService('quickbooks')
        
        if webhook_secret:
            is_valid = webhook_service.verify_signature(
                payload=payload,
                signature=signature,
                secret=webhook_secret,
                headers=request.META
            )
            
            if not is_valid:
                logger.error(f"Invalid QuickBooks webhook signature for integration {integration.id}")
                return Response(
                    {'error': 'Invalid signature'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        # Process webhook
        # QuickBooks sends multiple entities in one webhook
        event_type = 'data_change'
        event_id = f"qb_{realm_id}_{timezone.now().timestamp()}"
        
        webhook_event = webhook_service.process_webhook(
            integration=integration,
            event_type=event_type,
            payload=payload_data,
            event_id=event_id
        )
        
        return Response({'status': 'received', 'event_id': str(webhook_event.id)})
        
    except Exception as e:
        logger.error(f"Failed to process QuickBooks webhook: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def register_webhooks(request):
    """
    Register webhooks with a platform.
    
    Body params:
    - integration_id: Integration ID
    """
    from .services.webhook_service import WebhookService
    
    integration_id = request.data.get('integration_id')
    
    if not integration_id:
        return Response(
            {'error': 'integration_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        integration = Integration.objects.get(
            id=integration_id,
            organization=request.user.organization
        )
        
        webhook_service = WebhookService(integration.integration_type)
        result = webhook_service.register_webhooks(integration)
        
        return Response(result)
        
    except Integration.DoesNotExist:
        return Response(
            {'error': 'Integration not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Webhook registration failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
