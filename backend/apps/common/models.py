"""
Common models for Nova Ledger.
"""
from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class AuditLog(models.Model):
    """
    Comprehensive audit log for tracking all system changes.
    Critical for compliance (SOX, SOC 2, GDPR).
    """
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('ACCESS', 'Access'),
        ('EXPORT', 'Export'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('LOGIN_FAILED', 'Login Failed'),
        ('PERMISSION_DENIED', 'Permission Denied'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    username = models.CharField(max_length=150, blank=True)  # Store in case user is deleted
    user_role = models.CharField(max_length=50, blank=True)

    # Which organization
    organization = models.ForeignKey('accounts.Organization', on_delete=models.CASCADE, null=True, blank=True)

    # What
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)  # String representation

    # Changes
    changes = models.JSONField(default=dict, blank=True)  # {"field": {"old": "value", "new": "value"}}
    request_data = models.JSONField(default=dict, blank=True)  # Sanitized request data

    # Where
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)

    # When
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp', 'organization']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.username} - {self.action} - {self.model_name} - {self.timestamp}"
