# Nova Ledger API Documentation

## Base URL

- Development: `http://localhost:8000/api`
- Production: `https://api.novaledger.com/api`

## Authentication

Nova Ledger uses JWT (JSON Web Tokens) for authentication.

### Obtain Token

```http
POST /api/token/
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

### Refresh Token

```http
POST /api/token/refresh/
Content-Type: application/json

{
  "refresh": "your_refresh_token"
}
```

### Using the Token

Include the access token in the Authorization header:

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## Endpoints

### Transactions

#### List Transactions

```http
GET /api/transactions/
```

**Query Parameters:**
- `source_platform` (string): Filter by platform (shopify, stripe, amazon)
- `transaction_type` (string): Filter by type (sale, refund, payment)
- `start_date` (date): Start date filter (YYYY-MM-DD)
- `end_date` (date): End date filter
- `page` (integer): Page number
- `page_size` (integer): Items per page (default: 100)

**Response:**
```json
{
  "count": 1000,
  "next": "http://api.example.com/api/transactions/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "transaction_number": "STRIPE-12345",
      "transaction_type": "payment",
      "source_platform": "stripe",
      "transaction_date": "2024-01-15T10:30:00Z",
      "gross_amount": "250.00",
      "net_amount": "242.25",
      "fees": [
        {
          "fee_type": "payment_processing",
          "amount": "7.75"
        }
      ],
      "line_items": []
    }
  ]
}
```

#### Get Transaction Details

```http
GET /api/transactions/{id}/
```

#### Create Transaction

```http
POST /api/transactions/
Content-Type: application/json

{
  "transaction_type": "sale",
  "source_platform": "manual",
  "transaction_date": "2024-01-15T10:30:00Z",
  "description": "Manual sale entry",
  "gross_amount": "100.00",
  "net_amount": "95.00"
}
```

### Inventory

#### List Inventory Items

```http
GET /api/inventory/items/
```

**Query Parameters:**
- `sku` (string): Filter by SKU
- `category` (string): Filter by category
- `track_inventory` (boolean): Filter tracked items

**Response:**
```json
{
  "count": 500,
  "results": [
    {
      "id": "uuid",
      "sku": "WIDGET-001",
      "name": "Premium Widget",
      "current_average_cost": "15.50",
      "total_quantity_on_hand": "1250.000",
      "total_value": "19375.00",
      "costing_method": "average"
    }
  ]
}
```

#### Get Inventory Item

```http
GET /api/inventory/items/{id}/
```

#### Update Inventory Cost

```http
PATCH /api/inventory/items/{id}/
Content-Type: application/json

{
  "current_average_cost": "16.00"
}
```

### Integrations

#### List Integrations

```http
GET /api/integrations/
```

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "integration_type": "shopify",
      "name": "My Shopify Store",
      "is_connected": true,
      "last_sync_at": "2024-01-15T12:00:00Z",
      "auto_sync_enabled": true
    }
  ]
}
```

#### Connect Integration

```http
POST /api/integrations/connect/
Content-Type: application/json

{
  "integration_type": "shopify",
  "name": "My Store",
  "settings": {
    "shop_url": "mystore.myshopify.com"
  },
  "oauth_access_token": "your_token"
}
```

#### Trigger Sync

```http
POST /api/integrations/{id}/sync/
Content-Type: application/json

{
  "sync_type": "orders",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

**Response:**
```json
{
  "sync_log_id": "uuid",
  "status": "running",
  "started_at": "2024-01-15T12:00:00Z"
}
```

#### Get Sync Logs

```http
GET /api/integrations/{id}/sync-logs/
```

### Reporting

#### Get Dashboard Metrics

```http
GET /api/reporting/dashboard-metrics/
```

**Query Parameters:**
- `date_range` (string): 7d, 30d, 90d, 12m
- `start_date` (date): Custom start date
- `end_date` (date): Custom end date

**Response:**
```json
{
  "total_revenue": "284567.00",
  "gross_profit": "142890.00",
  "gross_margin": 50.2,
  "order_count": 1247,
  "average_order_value": "228.15",
  "anomalies_count": 5
}
```

#### Get Channel Profitability

```http
GET /api/reporting/channel-profitability/
```

**Query Parameters:**
- `period_type` (string): daily, weekly, monthly, quarterly
- `period_start` (date): Start date
- `period_end` (date): End date
- `channel_id` (uuid): Filter by specific channel

**Response:**
```json
{
  "results": [
    {
      "channel": {
        "id": "uuid",
        "name": "Shopify",
        "channel_type": "shopify"
      },
      "period_start": "2024-01-01",
      "period_end": "2024-01-31",
      "gross_sales": "95000.00",
      "net_sales": "90250.00",
      "total_cogs": "38000.00",
      "payment_processing_fees": "2750.00",
      "platform_fees": "4750.00",
      "gross_profit": "47500.00",
      "gross_margin_percent": 50.0,
      "net_profit": "44750.00",
      "net_margin_percent": 49.6
    }
  ]
}
```

#### Generate Profit & Loss Report

```http
POST /api/reporting/generate/
Content-Type: application/json

{
  "report_type": "profit_loss",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "channel_id": "uuid",  // optional
  "format": "json"  // json, pdf, excel, csv
}
```

**Response:**
```json
{
  "report_id": "uuid",
  "report_type": "profit_loss",
  "period_start": "2024-01-01",
  "period_end": "2024-01-31",
  "report_data": {
    "revenue": {
      "gross_sales": "284567.00",
      "returns_refunds": "-5250.00",
      "net_sales": "279317.00"
    },
    "cost_of_goods_sold": {
      "product_costs": "111726.80",
      "freight_in": "5586.34",
      "total_cogs": "117313.14"
    },
    "gross_profit": "162003.86",
    "operating_expenses": {
      "payment_processing_fees": "8089.51",
      "platform_fees": "11173.13",
      "shipping_expense": "4189.76",
      "total_expenses": "23452.40"
    },
    "net_profit": "138551.46"
  },
  "file_path": "/media/reports/pl_2024-01.pdf"
}
```

### Machine Learning / Anomalies

#### Get Anomalies

```http
GET /api/ml/anomalies/
```

**Query Parameters:**
- `status` (string): pending, reviewing, resolved, false_positive
- `severity` (string): low, medium, high, critical
- `anomaly_type` (string): unusual_fee, duplicate_transaction, etc.

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "anomaly_type": "unusual_fee",
      "severity": "high",
      "status": "pending",
      "description": "Stripe processing fee for transaction #12345 is 4.2% vs expected 2.9%",
      "transaction_id": "uuid",
      "expected_value": "7.25",
      "actual_value": "10.50",
      "confidence_score": 0.95,
      "detected_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### Review Anomaly

```http
POST /api/ml/anomalies/{id}/review/
Content-Type: application/json

{
  "status": "resolved",
  "resolution_notes": "Verified with Stripe - international transaction had higher fee"
}
```

### Revenue Recognition

#### Get Contracts

```http
GET /api/revenue/contracts/
```

#### Get Revenue Schedules

```http
GET /api/revenue/contracts/{id}/schedules/
```

#### Get SaaS Metrics

```http
GET /api/revenue/saas-metrics/
```

**Query Parameters:**
- `metric_type` (string): mrr, arr, churn_rate, ltv, cac
- `start_date` (date): Start date
- `end_date` (date): End date

**Response:**
```json
{
  "results": [
    {
      "metric_type": "mrr",
      "metric_date": "2024-01-31",
      "value": "45000.00",
      "calculation_details": {
        "new_mrr": "5000.00",
        "expansion_mrr": "2000.00",
        "contraction_mrr": "-500.00",
        "churned_mrr": "-1500.00"
      }
    }
  ]
}
```

## Webhooks

Nova Ledger can receive webhooks from integrated platforms for real-time sync.

### Webhook Endpoints

```http
POST /api/webhooks/shopify/
POST /api/webhooks/stripe/
POST /api/webhooks/paypal/
```

### Webhook Signature Verification

All webhooks are verified using HMAC signatures. Include your webhook secret in the integration settings.

## Rate Limiting

- **Standard Tier**: 1000 requests/hour
- **Pro Tier**: 5000 requests/hour
- **Enterprise Tier**: Unlimited

Rate limit headers are included in responses:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1642262400
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "status_code": 400,
    "detail": {
      "field_name": ["Error message"]
    },
    "type": "ValidationError"
  }
}
```

### Common HTTP Status Codes

- `200 OK`: Success
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

## Pagination

All list endpoints support pagination:

```json
{
  "count": 1000,
  "next": "http://api.example.com/api/endpoint/?page=2",
  "previous": null,
  "results": []
}
```

Use `page` and `page_size` query parameters to navigate.

## Interactive API Documentation

Visit the interactive API documentation at:
- **Swagger UI**: `http://localhost:8000/api/docs/`
- **OpenAPI Schema**: `http://localhost:8000/api/schema/`
