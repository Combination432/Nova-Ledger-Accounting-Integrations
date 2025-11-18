"""
Custom throttle classes for rate limiting.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """Throttle for burst requests - 100 requests per minute."""
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """Throttle for sustained requests - 10000 requests per day."""
    scope = 'sustained'


class WebhookRateThrottle(AnonRateThrottle):
    """Throttle for webhook endpoints - 1000 requests per hour."""
    scope = 'webhook'


class MLAnalysisRateThrottle(UserRateThrottle):
    """Throttle for expensive ML operations - 100 requests per hour."""
    scope = 'ml_analysis'


class ReportingRateThrottle(UserRateThrottle):
    """Throttle for reporting endpoints - 500 requests per hour."""
    scope = 'reporting'


class CalculationRateThrottle(UserRateThrottle):
    """Throttle for calculation-heavy endpoints - 200 requests per hour."""
    scope = 'calculation'
