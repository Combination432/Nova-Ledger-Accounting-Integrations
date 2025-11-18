"""
Logging filters to sanitize sensitive data from logs.
"""
import logging
import re


class SensitiveDataFilter(logging.Filter):
    """
    Filter to redact sensitive information from log messages.
    Prevents credential leakage through logs.
    """

    # Patterns to redact
    SENSITIVE_PATTERNS = [
        # API keys and secrets
        (r'(api[_-]?key|apikey)[\"\']?\s*[:=]\s*[\"\']?([^\s,\"\'}]+)', r'\1=***REDACTED***'),
        (r'(secret|password|passwd|pwd)[\"\']?\s*[:=]\s*[\"\']?([^\s,\"\'}]+)', r'\1=***REDACTED***'),
        (r'(token|auth)[\"\']?\s*[:=]\s*[\"\']?([^\s,\"\'}]+)', r'\1=***REDACTED***'),

        # Credit card numbers (basic pattern)
        (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '****-****-****-****'),

        # Social Security Numbers
        (r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', '***-**-****'),

        # Email addresses (partial redaction)
        (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'\1@***'),

        # Bearer tokens
        (r'Bearer\s+([A-Za-z0-9\-_\.]+)', 'Bearer ***REDACTED***'),

        # Connection strings
        (r'(postgres|mysql|mongodb)://([^:]+):([^@]+)@', r'\1://\2:***@'),
    ]

    def filter(self, record):
        """Sanitize the log record."""
        if hasattr(record, 'msg'):
            # Convert message to string
            msg = str(record.msg)

            # Apply all redaction patterns
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)

            record.msg = msg

        # Also sanitize args if they exist
        if hasattr(record, 'args') and record.args:
            sanitized_args = []
            for arg in record.args:
                arg_str = str(arg)
                for pattern, replacement in self.SENSITIVE_PATTERNS:
                    arg_str = re.sub(pattern, replacement, arg_str, flags=re.IGNORECASE)
                sanitized_args.append(arg_str)
            record.args = tuple(sanitized_args)

        return True


class PIIRedactionFilter(logging.Filter):
    """
    Filter to redact PII (Personally Identifiable Information) from logs.
    """

    def filter(self, record):
        """Redact PII from log records."""
        if hasattr(record, 'msg'):
            msg = str(record.msg)

            # Redact phone numbers
            msg = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '***-***-****', msg)

            # Redact long numbers (potentially sensitive)
            msg = re.sub(r'\b\d{10,}\b', '**REDACTED_NUMBER**', msg)

            record.msg = msg

        return True
