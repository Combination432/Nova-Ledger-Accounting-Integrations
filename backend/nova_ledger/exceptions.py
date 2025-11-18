"""
Custom exception handlers for Nova Ledger API.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Customize the response data
        custom_response_data = {
            'error': {
                'status_code': response.status_code,
                'detail': response.data,
                'type': exc.__class__.__name__
            }
        }
        response.data = custom_response_data

    # Log the exception
    logger.error(
        f"Exception occurred: {exc.__class__.__name__}",
        extra={'exception': str(exc), 'context': context}
    )

    return response


class IntegrationError(Exception):
    """Base exception for integration errors."""
    pass


class ReconciliationError(Exception):
    """Exception raised during reconciliation process."""
    pass


class InventoryError(Exception):
    """Exception raised during inventory operations."""
    pass


class TaxCalculationError(Exception):
    """Exception raised during tax calculations."""
    pass
