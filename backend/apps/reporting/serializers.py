"""
Serializers for reporting app.
"""
from rest_framework import serializers
from .models import (
    ChannelProfitability, ProductProfitability,
    DashboardMetric, FinancialReport, ReconciliationReport
)


class ChannelProfitabilitySerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source='sales_channel.name', read_only=True)
    channel_type = serializers.CharField(source='sales_channel.channel_type', read_only=True)
    
    class Meta:
        model = ChannelProfitability
        fields = '__all__'


class ProductProfitabilitySerializer(serializers.ModelSerializer):
    sku = serializers.CharField(source='inventory_item.sku', read_only=True)
    product_name = serializers.CharField(source='inventory_item.name', read_only=True)
    
    class Meta:
        model = ProductProfitability
        fields = '__all__'


class DashboardMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardMetric
        fields = '__all__'


class FinancialReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.CharField(source='generated_by.username', read_only=True)
    
    class Meta:
        model = FinancialReport
        fields = '__all__'


class ReconciliationReportSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(source='bank_account.account_name', read_only=True)
    
    class Meta:
        model = ReconciliationReport
        fields = '__all__'
