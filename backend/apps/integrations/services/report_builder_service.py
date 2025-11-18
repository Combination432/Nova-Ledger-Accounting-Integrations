"""
Custom report builder service.
Allows users to create custom reports with filters, grouping, and calculations.
"""
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import date, datetime
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from apps.transactions.models import Transaction
import logging

logger = logging.getLogger(__name__)


class ReportBuilderService:
    """
    Service for building custom reports.
    """

    def __init__(self, organization):
        """
        Initialize report builder service.

        Args:
            organization: Organization object
        """
        self.organization = organization

    def build_custom_report(
        self,
        report_config: Dict
    ) -> Dict:
        """
        Build a custom report based on configuration.

        Args:
            report_config: Report configuration dict with:
                - filters: List of filter conditions
                - group_by: List of fields to group by
                - aggregations: List of aggregations to calculate
                - sort_by: Field to sort by
                - columns: List of columns to include

        Returns:
            Dict with report data
        """
        # Parse configuration
        filters = report_config.get('filters', [])
        group_by = report_config.get('group_by', [])
        aggregations = report_config.get('aggregations', [])
        sort_by = report_config.get('sort_by')
        columns = report_config.get('columns', [])

        # Build queryset with filters
        queryset = self._apply_filters(filters)

        # Apply grouping and aggregations
        if group_by:
            results = self._apply_grouping(queryset, group_by, aggregations)
        else:
            results = self._apply_aggregations(queryset, aggregations)

        # Sort results
        if sort_by:
            results = self._apply_sorting(results, sort_by)

        # Format output
        report = {
            'generated_at': timezone.now().isoformat(),
            'config': report_config,
            'total_rows': len(results) if isinstance(results, list) else 1,
            'data': results
        }

        return report

    def _apply_filters(self, filters: List[Dict]) -> 'QuerySet':
        """
        Apply filters to transaction queryset.

        Args:
            filters: List of filter dicts

        Returns:
            Filtered queryset
        """
        queryset = Transaction.objects.filter(organization=self.organization)

        for filter_def in filters:
            field = filter_def.get('field')
            operator = filter_def.get('operator')
            value = filter_def.get('value')

            if operator == 'equals':
                queryset = queryset.filter(**{field: value})
            elif operator == 'not_equals':
                queryset = queryset.exclude(**{field: value})
            elif operator == 'contains':
                queryset = queryset.filter(**{f'{field}__icontains': value})
            elif operator == 'greater_than':
                queryset = queryset.filter(**{f'{field}__gt': value})
            elif operator == 'less_than':
                queryset = queryset.filter(**{f'{field}__lt': value})
            elif operator == 'greater_or_equal':
                queryset = queryset.filter(**{f'{field}__gte': value})
            elif operator == 'less_or_equal':
                queryset = queryset.filter(**{f'{field}__lte': value})
            elif operator == 'in':
                queryset = queryset.filter(**{f'{field}__in': value})
            elif operator == 'between':
                queryset = queryset.filter(**{
                    f'{field}__gte': value[0],
                    f'{field}__lte': value[1]
                })
            elif operator == 'is_null':
                queryset = queryset.filter(**{f'{field}__isnull': True})
            elif operator == 'is_not_null':
                queryset = queryset.filter(**{f'{field}__isnull': False})

        return queryset

    def _apply_grouping(
        self,
        queryset: 'QuerySet',
        group_by: List[str],
        aggregations: List[Dict]
    ) -> List[Dict]:
        """
        Apply grouping and aggregations.

        Args:
            queryset: Base queryset
            group_by: Fields to group by
            aggregations: Aggregation functions to apply

        Returns:
            List of grouped results
        """
        # Build aggregation dict
        agg_dict = {}

        for agg in aggregations:
            field = agg.get('field')
            function = agg.get('function')
            alias = agg.get('alias', f'{function}_{field}')

            if function == 'sum':
                agg_dict[alias] = Sum(field)
            elif function == 'avg':
                agg_dict[alias] = Avg(field)
            elif function == 'count':
                agg_dict[alias] = Count(field)
            elif function == 'min':
                agg_dict[alias] = Min(field)
            elif function == 'max':
                agg_dict[alias] = Max(field)

        # Apply grouping
        results = queryset.values(*group_by).annotate(**agg_dict)

        # Convert to list and serialize decimals
        return [self._serialize_row(row) for row in results]

    def _apply_aggregations(
        self,
        queryset: 'QuerySet',
        aggregations: List[Dict]
    ) -> Dict:
        """
        Apply aggregations without grouping.

        Args:
            queryset: Base queryset
            aggregations: Aggregation functions to apply

        Returns:
            Dict with aggregation results
        """
        if not aggregations:
            # Return count
            return {'total_count': queryset.count()}

        agg_dict = {}

        for agg in aggregations:
            field = agg.get('field')
            function = agg.get('function')
            alias = agg.get('alias', f'{function}_{field}')

            if function == 'sum':
                agg_dict[alias] = Sum(field)
            elif function == 'avg':
                agg_dict[alias] = Avg(field)
            elif function == 'count':
                agg_dict[alias] = Count(field)

        results = queryset.aggregate(**agg_dict)

        return self._serialize_row(results)

    def _apply_sorting(self, results, sort_by: str) -> List[Dict]:
        """
        Sort results.

        Args:
            results: Results to sort
            sort_by: Field to sort by (prefix with - for descending)

        Returns:
            Sorted results
        """
        if isinstance(results, list):
            reverse = sort_by.startswith('-')
            field = sort_by.lstrip('-')
            return sorted(results, key=lambda x: x.get(field, 0), reverse=reverse)
        else:
            return results

    def _serialize_row(self, row: Dict) -> Dict:
        """
        Serialize row values (convert Decimals, dates, etc.).

        Args:
            row: Row dict

        Returns:
            Serialized row
        """
        serialized = {}

        for key, value in row.items():
            if isinstance(value, Decimal):
                serialized[key] = float(value)
            elif isinstance(value, (date, datetime)):
                serialized[key] = value.isoformat()
            elif value is None:
                serialized[key] = None
            else:
                serialized[key] = value

        return serialized

    def get_available_fields(self) -> Dict:
        """
        Get list of available fields for report building.

        Returns:
            Dict with field definitions
        """
        return {
            'transaction_fields': [
                {'name': 'transaction_date', 'type': 'date', 'label': 'Transaction Date'},
                {'name': 'transaction_type', 'type': 'string', 'label': 'Type'},
                {'name': 'gross_amount', 'type': 'decimal', 'label': 'Gross Amount'},
                {'name': 'net_amount', 'type': 'decimal', 'label': 'Net Amount'},
                {'name': 'tax_amount', 'type': 'decimal', 'label': 'Tax Amount'},
                {'name': 'fee_amount', 'type': 'decimal', 'label': 'Fee Amount'},
                {'name': 'category', 'type': 'string', 'label': 'Category'},
                {'name': 'customer_name', 'type': 'string', 'label': 'Customer'},
                {'name': 'source_platform', 'type': 'string', 'label': 'Platform'},
                {'name': 'currency', 'type': 'string', 'label': 'Currency'},
                {'name': 'status', 'type': 'string', 'label': 'Status'},
            ],
            'aggregation_functions': [
                {'name': 'sum', 'label': 'Sum', 'applicable_types': ['decimal', 'integer']},
                {'name': 'avg', 'label': 'Average', 'applicable_types': ['decimal', 'integer']},
                {'name': 'count', 'label': 'Count', 'applicable_types': ['all']},
                {'name': 'min', 'label': 'Minimum', 'applicable_types': ['decimal', 'integer', 'date']},
                {'name': 'max', 'label': 'Maximum', 'applicable_types': ['decimal', 'integer', 'date']},
            ],
            'operators': [
                {'name': 'equals', 'label': 'Equals'},
                {'name': 'not_equals', 'label': 'Not Equals'},
                {'name': 'contains', 'label': 'Contains'},
                {'name': 'greater_than', 'label': 'Greater Than'},
                {'name': 'less_than', 'label': 'Less Than'},
                {'name': 'between', 'label': 'Between'},
                {'name': 'in', 'label': 'In'},
                {'name': 'is_null', 'label': 'Is Empty'},
                {'name': 'is_not_null', 'label': 'Is Not Empty'},
            ]
        }

    def save_report_template(
        self,
        name: str,
        description: str,
        config: Dict,
        user
    ) -> Dict:
        """
        Save a report template for reuse.

        Args:
            name: Template name
            description: Template description
            config: Report configuration
            user: User creating template

        Returns:
            Saved template
        """
        template = {
            'id': timezone.now().timestamp(),  # In production, use UUID
            'name': name,
            'description': description,
            'config': config,
            'created_by': user.get_full_name() if user else 'System',
            'created_at': timezone.now().isoformat(),
            'organization_id': str(self.organization.id)
        }

        # In production, save to ReportTemplate model
        logger.info(f"Saved report template: {name}")

        return template

    def get_report_templates(self) -> List[Dict]:
        """
        Get saved report templates for organization.

        Returns:
            List of templates
        """
        # In production, query from ReportTemplate model
        return [
            {
                'id': '1',
                'name': 'Monthly Revenue Summary',
                'description': 'Revenue grouped by month',
                'config': {
                    'filters': [
                        {'field': 'transaction_type', 'operator': 'equals', 'value': 'sale'}
                    ],
                    'group_by': ['transaction_date__month'],
                    'aggregations': [
                        {'field': 'gross_amount', 'function': 'sum', 'alias': 'total_revenue'}
                    ]
                }
            },
            {
                'id': '2',
                'name': 'Expenses by Category',
                'description': 'Expense breakdown by category',
                'config': {
                    'filters': [
                        {'field': 'transaction_type', 'operator': 'equals', 'value': 'expense'}
                    ],
                    'group_by': ['category'],
                    'aggregations': [
                        {'field': 'gross_amount', 'function': 'sum', 'alias': 'total_expense'},
                        {'field': 'id', 'function': 'count', 'alias': 'transaction_count'}
                    ],
                    'sort_by': '-total_expense'
                }
            }
        ]
