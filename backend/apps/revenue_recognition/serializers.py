"""
Serializers for revenue recognition app.
"""
from rest_framework import serializers
from .models import RevenueContract, RevenueSchedule, SubscriptionMetric, CustomerCohort


class RevenueScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RevenueSchedule
        fields = '__all__'


class RevenueContractSerializer(serializers.ModelSerializer):
    schedules = RevenueScheduleSerializer(many=True, read_only=True)
    
    class Meta:
        model = RevenueContract
        fields = '__all__'


class SubscriptionMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionMetric
        fields = '__all__'


class CustomerCohortSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerCohort
        fields = '__all__'
