"""
Custom permission classes for role-based access control.
"""
from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class that allows only owners and admins to perform write operations.
    Viewers and accountants have read-only access.
    """

    def has_permission(self, request, view):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Allow read operations for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write operations require owner or admin role
        return request.user.role in ['owner', 'admin']

    def has_object_permission(self, request, view, obj):
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only for owner and admin
        return request.user.role in ['owner', 'admin']


class IsOwnerOnly(permissions.BasePermission):
    """
    Permission class that allows only organization owners to perform actions.
    Used for critical operations like deleting organization, changing subscription, etc.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read operations allowed for all
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write operations only for owners
        return request.user.role == 'owner'

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.role == 'owner'


class CanManageFinancials(permissions.BasePermission):
    """
    Permission for managing financial data (transactions, journal entries).
    Allows owners, admins, and accountants.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read access for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write access for owner, admin, and accountant
        return request.user.role in ['owner', 'admin', 'accountant']

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.role in ['owner', 'admin', 'accountant']


class CanViewReports(permissions.BasePermission):
    """
    Permission for viewing reports.
    All authenticated users can view reports.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class BelongsToOrganization(permissions.BasePermission):
    """
    Object-level permission to ensure users can only access objects from their organization.
    """

    def has_object_permission(self, request, view, obj):
        # Get organization from object
        if hasattr(obj, 'organization'):
            return obj.organization == request.user.organization

        # For User objects, check if they belong to the same organization
        if hasattr(obj, 'organization_id'):
            return obj.organization_id == request.user.organization_id

        return False


class CanManageUsers(permissions.BasePermission):
    """
    Permission for managing users in the organization.
    Only owners and admins can manage users.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # View operations allowed for owner and admin
        if request.method in permissions.SAFE_METHODS:
            return request.user.role in ['owner', 'admin']

        # Write operations only for owner and admin
        return request.user.role in ['owner', 'admin']

    def has_object_permission(self, request, view, obj):
        # Can't modify users outside your organization
        if hasattr(obj, 'organization') and obj.organization != request.user.organization:
            return False

        # Owners and admins can manage users
        if request.user.role in ['owner', 'admin']:
            # But can't modify owner unless you're an owner
            if hasattr(obj, 'role') and obj.role == 'owner':
                return request.user.role == 'owner'
            return True

        return False
