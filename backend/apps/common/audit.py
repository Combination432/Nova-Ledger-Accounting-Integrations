"""
Audit logging utilities for manual audit trail creation.
"""
import logging
from django.conf import settings
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def log_audit_event(
    user,
    action: str,
    model_name: str,
    object_id: Optional[str] = None,
    object_repr: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    success: bool = True,
    error_message: str = '',
    request=None
):
    """
    Manually log an audit event.

    Args:
        user: User who performed the action
        action: Type of action (CREATE, UPDATE, DELETE, etc.)
        model_name: Name of the model affected
        object_id: ID of the object
        object_repr: String representation of the object
        changes: Dict of changes made
        success: Whether the action succeeded
        error_message: Error message if failed
        request: Django request object (optional)
    """
    try:
        from .models import AuditLog

        # Get organization
        organization = user.organization if hasattr(user, 'organization') else None

        # Get IP and user agent from request if available
        ip_address = None
        user_agent = ''
        request_path = ''
        request_method = ''

        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            request_path = request.path
            request_method = request.method

        AuditLog.objects.create(
            user=user if user.is_authenticated else None,
            username=user.username if user.is_authenticated else 'anonymous',
            user_role=user.role if hasattr(user, 'role') else '',
            organization=organization,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id else '',
            object_repr=str(object_repr) if object_repr else '',
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
            request_path=request_path,
            request_method=request_method,
            success=success,
            error_message=error_message
        )

    except Exception as e:
        # Never fail the main operation due to audit logging failure
        logger.error(f"Failed to create audit log: {str(e)}")


def get_model_changes(old_instance, new_instance, fields: Optional[list] = None):
    """
    Compare two model instances and return a dict of changes.

    Args:
        old_instance: Previous state of the model
        new_instance: New state of the model
        fields: List of fields to track (None = all fields)

    Returns:
        Dict of changes in format {"field": {"old": "value", "new": "value"}}
    """
    if old_instance is None:
        return {}

    changes = {}

    # Get fields to check
    if fields is None:
        fields = [f.name for f in new_instance._meta.fields if not f.name.startswith('_')]

    for field_name in fields:
        try:
            old_value = getattr(old_instance, field_name, None)
            new_value = getattr(new_instance, field_name, None)

            # Skip if values are the same
            if old_value == new_value:
                continue

            # Convert to string for JSON serialization
            changes[field_name] = {
                'old': str(old_value) if old_value is not None else None,
                'new': str(new_value) if new_value is not None else None,
            }

        except Exception as e:
            logger.debug(f"Error comparing field {field_name}: {str(e)}")
            continue

    return changes
