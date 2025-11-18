# Security Implementation Guide

This document outlines the comprehensive security measures implemented in Nova Ledger.

## 🔒 Implemented Security Features

### 1. Rate Limiting & Throttling ✅

**Protection Against**: API abuse, DoS attacks, brute force attacks

**Implementation**:
- Global rate limits: 1000 requests/hour per user, 100/hour for anonymous
- Burst protection: 100 requests/minute
- Endpoint-specific limits:
  - ML analysis: 100/hour
  - Reporting: 500/hour
  - Webhooks: 1000/hour
  - Calculations: 200/hour

**Configuration**: `backend/nova_ledger/settings.py`
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.common.throttles.BurstRateThrottle',
        'apps.common.throttles.SustainedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'burst': '100/min',
        ...
    }
}
```

**Files**:
- `backend/apps/common/throttles.py` - Custom throttle classes
- Applied to ML views, reporting views, and expensive operations

---

### 2. Object-Level Permissions & RBAC ✅

**Protection Against**: Horizontal privilege escalation, unauthorized data access

**Implementation**:
- Role-based access control (Owner, Admin, Accountant, Viewer)
- Object-level permissions ensure users only access their organization's data
- Permission classes:
  - `IsOwnerOnly` - Critical operations (delete org, change subscription)
  - `IsOwnerOrAdmin` - Administrative tasks (manage chart of accounts, channels)
  - `CanManageFinancials` - Accounting operations (owner, admin, accountant)
  - `BelongsToOrganization` - Data isolation by organization

**Files**:
- `backend/apps/common/permissions.py` - Permission classes
- Applied across all ViewSets in accounts, transactions, inventory, etc.

**Example**:
```python
class ChartOfAccountsViewSet(viewsets.ModelViewSet):
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwnerOrAdmin,
        BelongsToOrganization
    ]
```

---

### 3. Comprehensive Audit Logging ✅

**Protection Against**: Compliance violations, forensic blind spots

**Implementation**:
- Automatic logging of all mutations (POST, PUT, PATCH, DELETE)
- Tracks: user, action, model, changes, IP, timestamp, success/failure
- Middleware-based for automatic coverage
- Manual logging available via `log_audit_event()` utility

**Audit Log Fields**:
- Who: user, username, role
- What: action, model_name, object_id, changes
- Where: IP address, user agent, request path
- When: timestamp
- Status: success, error_message

**Files**:
- `backend/apps/common/models.py` - AuditLog model
- `backend/apps/common/middleware.py` - AuditLoggingMiddleware
- `backend/apps/common/audit.py` - Manual logging utilities

**Query Examples**:
```python
# Get all changes to a specific transaction
AuditLog.objects.filter(model_name='transactions', object_id='123')

# Get all failed login attempts
AuditLog.objects.filter(action='LOGIN_FAILED')

# Get all actions by a specific user
AuditLog.objects.filter(username='john@example.com')
```

---

### 4. JWT Security Hardening ✅

**Protection Against**: Token theft, replay attacks, long-lived compromise

**Improvements**:
- ✅ Access token lifetime: 15 minutes (was 1 hour)
- ✅ Refresh token lifetime: 1 day (was 7 days)
- ✅ Token rotation enabled
- ✅ Blacklisting after rotation
- ✅ Unique token IDs (JTI) for revocation
- ✅ Last login tracking

**Configuration**: `backend/nova_ledger/settings.py`
```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'JTI_CLAIM': 'jti',  # Unique token ID
}
```

**Best Practices**:
- Store tokens in httpOnly cookies (frontend)
- Implement token refresh before expiry
- Clear tokens on logout

---

### 5. Sensitive Data Sanitization in Logs ✅

**Protection Against**: Credential leakage, PII exposure

**Implementation**:
- Automatic redaction of sensitive patterns in all logs
- Filters applied to all logging handlers
- Patterns redacted:
  - API keys and secrets
  - Passwords and tokens
  - Credit card numbers
  - Social Security Numbers
  - Email addresses (partial)
  - Bearer tokens
  - Database connection strings

**Files**:
- `backend/apps/common/logging_filters.py` - SensitiveDataFilter, PIIRedactionFilter

**Example**:
```python
# Before: "API key: sk_live_abc123xyz"
# After:  "API key: ***REDACTED***"

# Before: "User email: john.doe@example.com"
# After:  "User email: john.doe@***"
```

---

### 6. Input Validation & Sanitization ✅

**Protection Against**: XSS, SQL injection, malicious input

**Implementation**:
- Custom validators for all input types
- NoHTMLValidator - prevents HTML/script tags
- NoSQLInjectionValidator - detects SQL injection patterns
- SafeDecimalValidator - prevents overflow attacks
- FileSizeValidator - prevents DoS via large files
- SecureFilenameValidator - prevents path traversal

**Files**:
- `backend/apps/common/validators.py` - Validation classes

**Usage Example**:
```python
from apps.common.validators import NoHTMLValidator, SafeDecimalValidator

class TransactionSerializer(serializers.ModelSerializer):
    description = serializers.CharField(
        max_length=500,
        validators=[NoHTMLValidator()]
    )
    gross_amount = serializers.DecimalField(
        max_digits=19,
        decimal_places=4,
        validators=[SafeDecimalValidator()]
    )
```

---

### 7. Encryption at Rest ✅

**Protection Against**: Database compromise, data breaches

**Implementation**:
- Custom encrypted field types for Django models
- Uses Fernet (AES-128 symmetric encryption)
- Automatic encryption/decryption on save/retrieve
- Fields: EncryptedTextField, EncryptedCharField

**Files**:
- `backend/apps/common/fields.py` - Encrypted field types

**Usage Example**:
```python
from apps.common.fields import EncryptedTextField

class Integration(models.Model):
    api_secret = EncryptedTextField()  # Automatically encrypted
```

**Configuration**:
Set `FIELD_ENCRYPTION_KEY` in environment:
```bash
# Generate a key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in .env:
FIELD_ENCRYPTION_KEY=your-generated-key-here
```

---

### 8. Request Size Limits ✅

**Protection Against**: DoS attacks via large payloads

**Implementation**:
- Middleware enforces 10MB max request size
- Early rejection before processing
- Logged for monitoring

**Files**:
- `backend/apps/common/middleware.py` - RequestSizeLimitMiddleware

**Configuration**:
```python
class RequestSizeLimitMiddleware:
    MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB
```

For production, also configure in nginx:
```nginx
client_max_body_size 10M;
```

---

### 9. API Versioning ✅

**Protection Against**: Breaking changes affecting production clients

**Implementation**:
- URL-based versioning: `/api/v1/...`
- Backwards compatibility maintained
- Explicit version negotiation

**Files**:
- `backend/nova_ledger/urls.py` - Versioned URL routes

**Configuration**: `backend/nova_ledger/settings.py`
```python
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.NamespaceVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1'],
}
```

**API Endpoints**:
- New format: `https://api.example.com/api/v1/transactions/`
- Legacy (backwards compat): `https://api.example.com/api/transactions/`

---

## 🔐 Additional Security Settings

### Production Security Headers

Configured in `settings.py` when `DEBUG=False`:

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### CORS Configuration

```python
CORS_ALLOWED_ORIGINS = [
    'https://app.example.com',  # Production frontend
]
CORS_ALLOW_CREDENTIALS = True
```

### Webhook Security

- HMAC signature verification for Shopify and Stripe webhooks
- Files: `backend/apps/integrations/webhooks.py`
- Automatic replay attack prevention via timestamp checking

---

## 📋 Security Checklist

### Before Production Deployment

- [ ] Set strong `DJANGO_SECRET_KEY` (64+ random characters)
- [ ] Generate and set `FIELD_ENCRYPTION_KEY`
- [ ] Configure `ALLOWED_HOSTS` with actual domains
- [ ] Set `DEBUG=False`
- [ ] Configure proper `CORS_ALLOWED_ORIGINS`
- [ ] Set up HTTPS/TLS certificates
- [ ] Configure Redis authentication (`requirepass`)
- [ ] Set up database connection pooling (pgbouncer)
- [ ] Enable Sentry for error monitoring
- [ ] Review and adjust rate limits based on usage patterns
- [ ] Set up regular database backups
- [ ] Configure log retention policies
- [ ] Enable WAF (Web Application Firewall)
- [ ] Set up monitoring and alerting

### Regular Security Maintenance

- [ ] Weekly: Review AuditLog for suspicious activity
- [ ] Monthly: Update dependencies (`pip-audit`)
- [ ] Monthly: Review and rotate API keys
- [ ] Quarterly: Security audit and penetration testing
- [ ] Quarterly: Review user permissions and roles
- [ ] Annually: Rotate encryption keys

---

## 🚨 Security Incident Response

If you suspect a security breach:

1. **Immediately**:
   - Revoke compromised API keys
   - Force logout all users (clear JWT blacklist)
   - Enable maintenance mode if needed

2. **Investigation**:
   - Query AuditLog for suspicious activity
   - Check failed login attempts
   - Review IP addresses and user agents

3. **Remediation**:
   - Patch vulnerability
   - Rotate all secrets
   - Notify affected users if PII exposed
   - Document incident and lessons learned

---

## 📚 Related Documentation

- **Audit Logs**: Query AuditLog model for compliance reporting
- **User Roles**: See `apps/accounts/models.py` User.role field
- **Permissions**: Review `apps/common/permissions.py`
- **Throttling**: Configure in `settings.py` REST_FRAMEWORK.DEFAULT_THROTTLE_RATES

---

## 🛡️ Compliance

This implementation supports:
- **SOC 2 Type II**: Audit logging, access controls, encryption
- **GDPR**: PII redaction, data encryption, audit trails
- **HIPAA**: Encryption at rest and in transit, access logging
- **PCI DSS**: Secure data storage, access controls, logging

---

## 🔗 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Django Security Best Practices](https://docs.djangoproject.com/en/5.0/topics/security/)
- [DRF Security](https://www.django-rest-framework.org/topics/security/)
- [CWE Top 25](https://cwe.mitre.org/top25/)

---

**Last Updated**: 2025-11-18
**Security Version**: 1.0
