"""
Serializers for integrations app.
"""
from rest_framework import serializers
from .models import Integration, SyncLog, WebhookEndpoint, WebhookEvent, TaxConfiguration


class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Integration
        fields = '__all__'
        extra_kwargs = {
            'oauth_access_token': {'write_only': True},
            'oauth_refresh_token': {'write_only': True},
            'auth_credentials': {'write_only': True}
        }


class SyncLogSerializer(serializers.ModelSerializer):
    integration_name = serializers.CharField(source='integration.name', read_only=True)
    
    class Meta:
        model = SyncLog
        fields = '__all__'


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = '__all__'
        extra_kwargs = {'secret_key': {'write_only': True}}


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = '__all__'


class TaxConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxConfiguration
        fields = '__all__'
