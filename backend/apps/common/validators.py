"""
Custom validators for enhanced input validation.
"""
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import re


class NoHTMLValidator(RegexValidator):
    """Validator to prevent HTML/script injection in text fields."""
    regex = r'^[^<>]*$'
    message = 'HTML tags are not allowed'
    code = 'invalid_html'


class NoSQLInjectionValidator:
    """Validator to prevent common SQL injection patterns."""

    DANGEROUS_PATTERNS = [
        r'(\bSELECT\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b|\bDROP\b|\bCREATE\b|\bALTER\b)',
        r'(--|;|\/\*|\*\/)',
        r'(\bUNION\b|\bEXEC\b|\bEXECUTE\b)',
    ]

    def __call__(self, value):
        """Check if value contains SQL injection patterns."""
        if not isinstance(value, str):
            return

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise ValidationError(
                    'Invalid characters detected',
                    code='sql_injection'
                )


class SafeDecimalValidator:
    """Validator to ensure decimal values are within safe ranges."""

    def __init__(self, max_digits=19, decimal_places=4, min_value=None, max_value=None):
        self.max_digits = max_digits
        self.decimal_places = decimal_places
        self.min_value = Decimal(str(min_value)) if min_value is not None else Decimal('0.0001')
        self.max_value = Decimal(str(max_value)) if max_value is not None else Decimal('999999999999')

    def __call__(self, value):
        """Validate decimal value."""
        if value is None:
            return

        try:
            decimal_value = Decimal(str(value))
        except (ValueError, TypeError):
            raise ValidationError('Invalid decimal value')

        if decimal_value < self.min_value:
            raise ValidationError(f'Value must be at least {self.min_value}')

        if decimal_value > self.max_value:
            raise ValidationError(f'Value cannot exceed {self.max_value}')

        # Check total digits
        value_str = str(decimal_value).replace('.', '').replace('-', '')
        if len(value_str) > self.max_digits:
            raise ValidationError(f'Value has too many digits (max: {self.max_digits})')


class AlphanumericValidator(RegexValidator):
    """Validator for alphanumeric with limited special characters."""
    regex = r'^[a-zA-Z0-9\s\-_.]+$'
    message = 'Only alphanumeric characters, spaces, hyphens, underscores, and periods are allowed'
    code = 'invalid_characters'


class EmailListValidator:
    """Validator for comma-separated email list."""

    def __call__(self, value):
        """Validate email list."""
        if not value:
            return

        emails = [email.strip() for email in value.split(',')]
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for email in emails:
            if not re.match(email_regex, email):
                raise ValidationError(f'Invalid email address: {email}')


class FileSizeValidator:
    """Validator to check file upload size."""

    def __init__(self, max_size_mb=10):
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes

    def __call__(self, value):
        """Validate file size."""
        if value.size > self.max_size:
            raise ValidationError(
                f'File size cannot exceed {self.max_size / (1024 * 1024):.0f}MB'
            )


class SecureFilenameValidator:
    """Validator to ensure safe filenames."""

    DANGEROUS_PATTERNS = [
        r'\.\.',  # Path traversal
        r'[\\/]',  # Directory separators
        r'[<>:"|?*]',  # Windows reserved characters
    ]

    def __call__(self, value):
        """Validate filename."""
        filename = value.name if hasattr(value, 'name') else str(value)

        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, filename):
                raise ValidationError(
                    'Filename contains invalid characters',
                    code='unsafe_filename'
                )

        # Check for null bytes
        if '\x00' in filename:
            raise ValidationError('Filename contains null bytes')


def validate_no_script_tags(value):
    """Validate that value doesn't contain script tags."""
    if '<script' in value.lower() or 'javascript:' in value.lower():
        raise ValidationError('Script tags and javascript: protocol are not allowed')


def validate_safe_url(value):
    """Validate that URL is safe (no javascript:, data:, etc.)."""
    dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']

    for protocol in dangerous_protocols:
        if value.lower().startswith(protocol):
            raise ValidationError(f'URL protocol {protocol} is not allowed')
