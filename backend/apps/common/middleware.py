"""
Custom middleware for Nova Ledger.
"""
import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
from .audit import log_audit_event

logger = logging.getLogger(__name__)


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log API requests for audit purposes.
    """

    # Methods that trigger audit logs
    AUDIT_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE']

    # Paths to exclude from audit logging
    EXCLUDE_PATHS = [
        '/api/token/',
        '/api/token/refresh/',
        '/api/schema/',
        '/api/docs/',
        '/admin/jsi18n/',
    ]

    def process_request(self, request):
        """Store request start time for later use."""
        import time
        request._audit_start_time = time.time()
        return None

    def process_response(self, request, response):
        """Log audit trail for mutations."""
        # Skip if not an API request
        if not request.path.startswith('/api/'):
            return response

        # Skip excluded paths
        if any(request.path.startswith(path) for path in self.EXCLUDE_PATHS):
            return response

        # Only log mutations (POST, PUT, PATCH, DELETE)
        if request.method not in self.AUDIT_METHODS:
            return response

        # Log the audit event
        try:
            self._log_request(request, response)
        except Exception as e:
            logger.error(f"Failed to log audit event: {str(e)}")

        return response

    def _log_request(self, request, response):
        """Create audit log entry."""
        from .models import AuditLog

        # Determine action
        action_map = {
            'POST': 'CREATE',
            'PUT': 'UPDATE',
            'PATCH': 'UPDATE',
            'DELETE': 'DELETE',
        }
        action = action_map.get(request.method, 'ACCESS')

        # Get user info
        user = request.user if request.user.is_authenticated else None
        username = user.username if user else 'anonymous'
        user_role = user.role if user and hasattr(user, 'role') else ''
        organization = user.organization if user and hasattr(user, 'organization') else None

        # Determine success
        success = 200 <= response.status_code < 300

        # Get IP address
        ip_address = self._get_client_ip(request)

        # Create audit log (async to avoid slowing down requests)
        AuditLog.objects.create(
            user=user,
            username=username,
            user_role=user_role,
            organization=organization,
            action=action,
            model_name=self._extract_model_from_path(request.path),
            request_path=request.path,
            request_method=request.method,
            ip_address=ip_address,
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
            success=success,
            error_message='' if success else f'Status: {response.status_code}'
        )

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def _extract_model_from_path(path):
        """Extract model name from API path."""
        # Example: /api/transactions/123/ -> transactions
        parts = [p for p in path.split('/') if p]
        if len(parts) >= 2 and parts[0] == 'api':
            return parts[1]
        return 'unknown'


class RequestSizeLimitMiddleware(MiddlewareMixin):
    """
    Middleware to limit request body size.
    Prevents DoS attacks via large payloads.
    """

    # Maximum request size in bytes (10 MB)
    MAX_REQUEST_SIZE = 10 * 1024 * 1024

    def process_request(self, request):
        """Check request size before processing."""
        if request.content_length and request.content_length > self.MAX_REQUEST_SIZE:
            logger.warning(
                f"Request size limit exceeded: {request.content_length} bytes from {request.META.get('REMOTE_ADDR')}"
            )
            return HttpResponse(
                'Request entity too large. Maximum size is 10MB.',
                status=413,
                content_type='text/plain'
            )
        return None
