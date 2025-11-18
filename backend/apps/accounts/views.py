"""
API views for accounts app.
"""
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.common.permissions import IsOwnerOnly, IsOwnerOrAdmin, BelongsToOrganization
from .models import Organization, ChartOfAccounts, SalesChannel
from .serializers import (
    OrganizationSerializer,
    ChartOfAccountsSerializer,
    SalesChannelSerializer,
    UserSerializer
)
from django.contrib.auth import get_user_model

User = get_user_model()


class OrganizationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing organizations.
    """
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOnly, BelongsToOrganization]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'tax_id']
    ordering_fields = ['name', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        # Users can only see their own organization
        if self.request.user.is_superuser:
            return Organization.objects.all()
        return Organization.objects.filter(id=self.request.user.organization_id)

    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Get all users in this organization."""
        organization = self.get_object()
        users = organization.users.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class ChartOfAccountsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing chart of accounts.
    """
    serializer_class = ChartOfAccountsSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin, BelongsToOrganization]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['account_type', 'account_subtype', 'is_active', 'is_sub_account']
    search_fields = ['account_number', 'account_name', 'description']
    ordering_fields = ['account_number', 'account_name', 'created_at']
    ordering = ['account_number']

    def get_queryset(self):
        return ChartOfAccounts.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get accounts grouped by type."""
        accounts = self.get_queryset()
        grouped = {}
        for account_type, _ in ChartOfAccounts.ACCOUNT_TYPES:
            grouped[account_type] = ChartOfAccountsSerializer(
                accounts.filter(account_type=account_type),
                many=True
            ).data
        return Response(grouped)

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """Get current balance for an account."""
        account = self.get_object()
        return Response({
            'account_id': account.id,
            'account_name': account.account_name,
            'current_balance': account.current_balance,
            'account_type': account.account_type
        })


class SalesChannelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing sales channels.
    """
    serializer_class = SalesChannelSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin, BelongsToOrganization]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['channel_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return SalesChannel.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)

    @action(detail=True, methods=['get'])
    def profitability(self, request, pk=None):
        """Get profitability data for this channel."""
        from apps.reporting.models import ChannelProfitability
        from apps.reporting.serializers import ChannelProfitabilitySerializer

        channel = self.get_object()
        profitability = ChannelProfitability.objects.filter(
            sales_channel=channel
        ).order_by('-period_start')[:12]  # Last 12 periods

        serializer = ChannelProfitabilitySerializer(profitability, many=True)
        return Response(serializer.data)
