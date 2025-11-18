"""
Audit trail logging service.
Tracks all changes to transactions, integrations, and other critical entities.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import json
import logging

logger = logging.getLogger(__name__)


class AuditTrailService:
    """
    Service for audit trail logging and querying.
    """

    def __init__(self, organization):
        """
        Initialize audit trail service.

        Args:
            organization: Organization object
        """
        self.organization = organization

    def log_change(
        self,
        user,
        action: str,
        entity_type: str,
        entity_id: str,
        changes: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Log a change to an entity.

        Args:
            user: User making the change
            action: Action type (create, update, delete, approve, etc.)
            entity_type: Type of entity (transaction, integration, rule, etc.)
            entity_id: ID of the entity
            changes: Dict with before/after values
            metadata: Additional metadata

        Returns:
            Created audit log entry
        """
        audit_entry = {
            'timestamp': timezone.now().isoformat(),
            'organization_id': str(self.organization.id),
            'user_id': str(user.id) if user else None,
            'user_name': user.get_full_name() if user else 'System',
            'user_email': user.email if user else None,
            'action': action,
            'entity_type': entity_type,
            'entity_id': entity_id,
            'changes': changes or {},
            'metadata': metadata or {},
            'ip_address': metadata.get('ip_address') if metadata else None,
            'user_agent': metadata.get('user_agent') if metadata else None
        }

        # In production, store in dedicated audit log table or service
        # For now, log to file/console
        logger.info(f"AUDIT: {json.dumps(audit_entry)}")

        # Also store in metadata of the entity if possible
        self._attach_to_entity(entity_type, entity_id, audit_entry)

        return audit_entry

    def log_transaction_change(
        self,
        user,
        transaction,
        action: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Log a change to a transaction.

        Args:
            user: User making the change
            transaction: Transaction object
            action: Action type
            old_values: Previous values
            new_values: New values
            metadata: Additional metadata

        Returns:
            Audit log entry
        """
        changes = {}

        if old_values and new_values:
            # Calculate what changed
            for key in new_values.keys():
                old_val = old_values.get(key)
                new_val = new_values.get(key)

                if old_val != new_val:
                    changes[key] = {
                        'before': self._serialize_value(old_val),
                        'after': self._serialize_value(new_val)
                    }

        return self.log_change(
            user=user,
            action=action,
            entity_type='transaction',
            entity_id=str(transaction.id),
            changes=changes,
            metadata={
                **(metadata or {}),
                'transaction_date': transaction.transaction_date.isoformat(),
                'transaction_type': transaction.transaction_type,
                'amount': float(transaction.gross_amount),
                'source_platform': transaction.source_platform
            }
        )

    def log_bulk_operation(
        self,
        user,
        operation: str,
        entity_type: str,
        entity_ids: List[str],
        parameters: Dict,
        results: Dict,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Log a bulk operation.

        Args:
            user: User performing operation
            operation: Operation type (batch_categorize, batch_delete, etc.)
            entity_type: Type of entities
            entity_ids: List of entity IDs
            parameters: Operation parameters
            results: Operation results
            metadata: Additional metadata

        Returns:
            Audit log entry
        """
        return self.log_change(
            user=user,
            action=f'bulk_{operation}',
            entity_type=entity_type,
            entity_id='bulk',
            changes={
                'entities_affected': len(entity_ids),
                'parameters': parameters,
                'results': results
            },
            metadata={
                **(metadata or {}),
                'entity_ids': entity_ids[:100],  # Store first 100 IDs
                'total_entities': len(entity_ids)
            }
        )

    def log_integration_event(
        self,
        user,
        integration,
        event: str,
        details: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Log an integration-related event.

        Args:
            user: User (or None for system events)
            integration: Integration object
            event: Event type (connected, disconnected, sync_started, etc.)
            details: Event details
            metadata: Additional metadata

        Returns:
            Audit log entry
        """
        return self.log_change(
            user=user,
            action=event,
            entity_type='integration',
            entity_id=str(integration.id),
            changes=details or {},
            metadata={
                **(metadata or {}),
                'integration_type': integration.integration_type,
                'integration_name': integration.name
            }
        )

    def get_audit_trail(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Query audit trail.

        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            user_id: Filter by user
            action: Filter by action type
            start_date: Filter by date range start
            end_date: Filter by date range end
            limit: Maximum results to return

        Returns:
            List of audit log entries
        """
        # In production, query from dedicated audit log storage
        # For now, return sample structure

        # This would query a dedicated AuditLog model in production
        filters = []

        if entity_type:
            filters.append(Q(entity_type=entity_type))
        if entity_id:
            filters.append(Q(entity_id=entity_id))
        if user_id:
            filters.append(Q(user_id=user_id))
        if action:
            filters.append(Q(action=action))
        if start_date:
            filters.append(Q(timestamp__gte=start_date))
        if end_date:
            filters.append(Q(timestamp__lte=end_date))

        # Sample audit log entries
        # In production, this would query actual audit log table
        return []

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[Dict]:
        """
        Get complete change history for an entity.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID

        Returns:
            List of changes in chronological order
        """
        return self.get_audit_trail(
            entity_type=entity_type,
            entity_id=entity_id
        )

    def get_user_activity(
        self,
        user_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get activity log for a user.

        Args:
            user_id: User ID
            start_date: Start date
            end_date: End date
            limit: Maximum results

        Returns:
            List of user actions
        """
        return self.get_audit_trail(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )

    def generate_audit_report(
        self,
        start_date: date,
        end_date: date,
        include_details: bool = True
    ) -> Dict:
        """
        Generate audit report for a date range.

        Args:
            start_date: Report start date
            end_date: Report end date
            include_details: Include detailed change log

        Returns:
            Dict with audit report
        """
        audit_logs = self.get_audit_trail(
            start_date=start_date,
            end_date=end_date,
            limit=10000
        )

        # Aggregate statistics
        stats = {
            'total_actions': len(audit_logs),
            'by_action_type': {},
            'by_entity_type': {},
            'by_user': {},
            'by_date': {}
        }

        for log in audit_logs:
            # Count by action type
            action = log.get('action', 'unknown')
            stats['by_action_type'][action] = stats['by_action_type'].get(action, 0) + 1

            # Count by entity type
            entity_type = log.get('entity_type', 'unknown')
            stats['by_entity_type'][entity_type] = stats['by_entity_type'].get(entity_type, 0) + 1

            # Count by user
            user_name = log.get('user_name', 'Unknown')
            stats['by_user'][user_name] = stats['by_user'].get(user_name, 0) + 1

            # Count by date
            timestamp = log.get('timestamp', '')
            log_date = timestamp.split('T')[0] if timestamp else 'unknown'
            stats['by_date'][log_date] = stats['by_date'].get(log_date, 0) + 1

        report = {
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'statistics': stats
        }

        if include_details:
            report['audit_logs'] = audit_logs

        return report

    def _serialize_value(self, value: Any) -> Any:
        """
        Serialize value for audit log.

        Args:
            value: Value to serialize

        Returns:
            Serialized value
        """
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        elif hasattr(value, 'id'):
            # Model instance
            return str(value.id)
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        else:
            return value

    def _attach_to_entity(
        self,
        entity_type: str,
        entity_id: str,
        audit_entry: Dict
    ):
        """
        Attach audit entry to entity's metadata.

        Args:
            entity_type: Entity type
            entity_id: Entity ID
            audit_entry: Audit entry to attach
        """
        try:
            # Attach audit log to entity's metadata
            if entity_type == 'transaction':
                from apps.transactions.models import Transaction
                txn = Transaction.objects.get(id=entity_id)
                txn.metadata = txn.metadata or {}
                txn.metadata['audit_trail'] = txn.metadata.get('audit_trail', [])
                txn.metadata['audit_trail'].append({
                    'timestamp': audit_entry['timestamp'],
                    'user': audit_entry['user_name'],
                    'action': audit_entry['action'],
                    'changes': audit_entry.get('changes', {})
                })
                # Keep only last 50 audit entries
                txn.metadata['audit_trail'] = txn.metadata['audit_trail'][-50:]
                txn.save(update_fields=['metadata'])

        except Exception as e:
            logger.warning(f"Failed to attach audit entry to entity: {str(e)}")

    def track_field_changes(
        self,
        old_instance,
        new_instance,
        tracked_fields: List[str]
    ) -> Dict:
        """
        Track changes between old and new instance.

        Args:
            old_instance: Previous instance
            new_instance: Updated instance
            tracked_fields: List of field names to track

        Returns:
            Dict with before/after values for changed fields
        """
        changes = {}

        for field in tracked_fields:
            old_value = getattr(old_instance, field, None)
            new_value = getattr(new_instance, field, None)

            if old_value != new_value:
                changes[field] = {
                    'before': self._serialize_value(old_value),
                    'after': self._serialize_value(new_value)
                }

        return changes

    def log_api_access(
        self,
        user,
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_time_ms: Optional[float] = None
    ) -> Dict:
        """
        Log API access for security and monitoring.

        Args:
            user: User making the request
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            ip_address: Client IP address
            user_agent: Client user agent
            request_data: Request payload (sanitized)
            response_time_ms: Response time in milliseconds

        Returns:
            API access log entry
        """
        access_log = {
            'timestamp': timezone.now().isoformat(),
            'user_id': str(user.id) if user else None,
            'user_email': user.email if user else None,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_data': request_data,
            'response_time_ms': response_time_ms
        }

        logger.info(f"API_ACCESS: {json.dumps(access_log)}")

        return access_log
