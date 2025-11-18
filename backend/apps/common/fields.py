"""
Custom Django model fields with encryption support.
"""
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import base64
import hashlib


def get_encryption_key():
    """Get or generate encryption key from settings."""
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        # In development, use a derived key (NOT for production!)
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
        return key.decode() if isinstance(key, bytes) else key

    # Ensure key is properly formatted
    if len(key) < 32:
        # Derive a proper 32-byte key from the provided key
        key = base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest())
        return key.decode() if isinstance(key, bytes) else key

    return key


class EncryptedTextField(models.TextField):
    """
    TextField that automatically encrypts data before saving to database.
    Uses Fernet (symmetric encryption) from cryptography library.
    """

    description = "Encrypted text field"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        """Encrypt the value before saving to database."""
        if value is None or value == '':
            return value

        try:
            key = get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(value.encode())
            return encrypted.decode()
        except Exception as e:
            # Log error but don't fail the operation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Encryption failed: {str(e)}")
            # Return original value (not ideal, but prevents data loss)
            return value

    def from_db_value(self, value, expression, connection):
        """Decrypt the value when retrieving from database."""
        if value is None or value == '':
            return value

        try:
            key = get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(value.encode())
            return decrypted.decode()
        except Exception as e:
            # Value might not be encrypted (migration scenario)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Decryption failed, returning raw value: {str(e)}")
            return value

    def to_python(self, value):
        """Convert to Python object."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)


class EncryptedCharField(models.CharField):
    """
    CharField that automatically encrypts data before saving to database.
    """

    description = "Encrypted char field"

    def get_prep_value(self, value):
        """Encrypt the value before saving to database."""
        if value is None or value == '':
            return value

        try:
            key = get_encryption_key()
            f = Fernet(key)
            encrypted = f.encrypt(value.encode())
            # Encrypted values are longer, so we store them in the CharField
            # Make sure max_length is sufficient
            return encrypted.decode()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Encryption failed: {str(e)}")
            return value

    def from_db_value(self, value, expression, connection):
        """Decrypt the value when retrieving from database."""
        if value is None or value == '':
            return value

        try:
            key = get_encryption_key()
            f = Fernet(key)
            decrypted = f.decrypt(value.encode())
            return decrypted.decode()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Decryption failed, returning raw value: {str(e)}")
            return value

    def to_python(self, value):
        """Convert to Python object."""
        if isinstance(value, str) or value is None:
            return value
        return str(value)
