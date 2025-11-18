"""
Serializers for ML app.
"""
from rest_framework import serializers
from .models import AnomalyDetection, FinancialForecast, TransactionCategorization


class AnomalyDetectionSerializer(serializers.ModelSerializer):
    transaction_number = serializers.CharField(source='transaction.transaction_number', read_only=True, allow_null=True)
    
    class Meta:
        model = AnomalyDetection
        fields = '__all__'


class FinancialForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialForecast
        fields = '__all__'


class TransactionCategorizationSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='suggested_account.account_name', read_only=True)
    
    class Meta:
        model = TransactionCategorization
        fields = '__all__'
