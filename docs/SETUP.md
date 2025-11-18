# Nova Ledger Setup Guide

This guide will walk you through setting up Nova Ledger on your local machine or in production.

## Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **PostgreSQL 16+** (with TimescaleDB extension)
- **Redis 7+**
- **Docker & Docker Compose** (recommended for easy setup)

## Quick Start with Docker

The fastest way to get Nova Ledger running is using Docker Compose:

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/nova-ledger.git
cd nova-ledger
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys for integrations (Shopify, Stripe, QuickBooks, etc.)

### 3. Start All Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL with TimescaleDB
- Redis
- Kafka + Zookeeper
- Django Backend (on port 8000)
- Next.js Frontend (on port 3000)
- Celery Worker
- Celery Beat

### 4. Run Migrations

```bash
docker-compose exec backend python manage.py migrate
```

### 5. Create Superuser

```bash
docker-compose exec backend python manage.py createsuperuser
```

### 6. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs/
- **Django Admin**: http://localhost:8000/admin/

## Manual Setup (Without Docker)

### Backend Setup

1. **Create Virtual Environment**

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install Dependencies**

```bash
pip install -r requirements.txt
```

3. **Set Up PostgreSQL**

```bash
# Create database
createdb nova_ledger

# Enable TimescaleDB extension
psql nova_ledger
> CREATE EXTENSION IF NOT EXISTS timescaledb;
```

4. **Configure Environment**

```bash
cp ../.env.example ../.env
# Edit .env with your settings
```

5. **Run Migrations**

```bash
python manage.py migrate
```

6. **Create Superuser**

```bash
python manage.py createsuperuser
```

7. **Start Development Server**

```bash
python manage.py runserver
```

### Frontend Setup

1. **Install Dependencies**

```bash
cd frontend
npm install
```

2. **Configure Environment**

```bash
# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

3. **Start Development Server**

```bash
npm run dev
```

### Celery Setup (for background tasks)

1. **Start Redis**

```bash
redis-server
```

2. **Start Celery Worker**

```bash
cd backend
celery -A nova_ledger worker -l info
```

3. **Start Celery Beat (for scheduled tasks)**

```bash
celery -A nova_ledger beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Kafka Setup (for real-time streaming)

1. **Start Zookeeper**

```bash
zookeeper-server-start /path/to/kafka/config/zookeeper.properties
```

2. **Start Kafka**

```bash
kafka-server-start /path/to/kafka/config/server.properties
```

## Configuration

### Integration Setup

#### Shopify

1. Create a Shopify App in your Shopify Partner Dashboard
2. Add the API credentials to `.env`:
   ```
   SHOPIFY_API_KEY=your_api_key
   SHOPIFY_API_SECRET=your_api_secret
   ```
3. In Nova Ledger, navigate to Integrations → Add Integration → Shopify
4. Follow the OAuth flow to connect your store

#### Stripe

1. Get your Stripe API keys from https://dashboard.stripe.com/apikeys
2. Add to `.env`:
   ```
   STRIPE_API_KEY=sk_test_your_key
   ```
3. In Nova Ledger, navigate to Integrations → Add Integration → Stripe

#### QuickBooks Online

1. Create a QuickBooks App at https://developer.intuit.com/
2. Add credentials to `.env`:
   ```
   QUICKBOOKS_CLIENT_ID=your_client_id
   QUICKBOOKS_CLIENT_SECRET=your_client_secret
   ```
3. In Nova Ledger, navigate to Integrations → Add Integration → QuickBooks
4. Complete the OAuth flow

### Database Optimization

For production, enable TimescaleDB hypertables for better time-series performance:

```sql
-- Connect to your database
psql nova_ledger

-- Create hypertables for time-series data
SELECT create_hypertable('transactions', 'transaction_date');
SELECT create_hypertable('inventory_transactions', 'transaction_date');
SELECT create_hypertable('journal_entries', 'entry_date');

-- Create retention policies (optional)
SELECT add_retention_policy('transactions', INTERVAL '7 years');
```

## Production Deployment

### Environment Variables

Ensure these are set in production:

```bash
DEBUG=False
SECRET_KEY=your-very-secret-key
ALLOWED_HOSTS=yourdomain.com
DB_HOST=your-db-host
DB_PASSWORD=secure-password
SENTRY_DSN=your-sentry-dsn
```

### Security Checklist

- [ ] Change `SECRET_KEY` to a secure random string
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use HTTPS (SSL certificates)
- [ ] Enable CSRF protection
- [ ] Set up firewall rules
- [ ] Enable database backups
- [ ] Configure Sentry for error monitoring
- [ ] Set up log rotation

### Deployment Options

#### AWS

Use the provided CloudFormation templates in `/infrastructure/aws/`

#### Kubernetes

Use the Helm charts in `/infrastructure/k8s/`

#### Heroku

```bash
heroku create nova-ledger
heroku addons:create heroku-postgresql:standard-0
heroku addons:create heroku-redis:premium-0
git push heroku main
heroku run python backend/manage.py migrate
```

## Testing

### Backend Tests

```bash
cd backend
pytest
```

### Frontend Tests

```bash
cd frontend
npm test
```

### Integration Tests

```bash
cd backend
pytest tests/integration
```

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `pg_isready`
- Check connection settings in `.env`
- Ensure database exists: `psql -l`

### API Connection Issues

- Check backend is running: `curl http://localhost:8000/api/`
- Verify CORS settings in `backend/nova_ledger/settings.py`
- Check frontend `.env.local` has correct API_URL

### Celery Not Processing Tasks

- Ensure Redis is running: `redis-cli ping`
- Check Celery worker logs
- Verify `CELERY_BROKER_URL` in `.env`

## Support

For issues and questions:
- GitHub Issues: https://github.com/yourusername/nova-ledger/issues
- Documentation: https://docs.novaledger.com
- Email: support@novaledger.com
