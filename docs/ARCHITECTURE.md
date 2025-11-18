# Nova Ledger Architecture

## System Overview

Nova Ledger is a cloud-native, microservices-oriented accounting automation platform designed for high availability, scalability, and real-time processing.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
│                                                                   │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐     │
│  │  Next.js   │  │   React      │  │   TailwindCSS       │     │
│  │  SSR/SSG   │  │  Components  │  │   Styling           │     │
│  └────────────┘  └──────────────┘  └─────────────────────┘     │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS/REST API
┌───────────────────────────┴─────────────────────────────────────┐
│                      API Gateway / Load Balancer                 │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────┴─────────────────────────────────────┐
│                      Application Layer (Django)                  │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ Transactions │  │  Inventory   │  │  Integrations    │      │
│  │   Service    │  │   Service    │  │    Service       │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │  Reporting   │  │   Revenue    │  │   ML/Anomaly     │      │
│  │   Service    │  │Recognition   │  │   Detection      │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
└────┬──────────────────┬─────────────────┬────────────────────┬──┘
     │                  │                 │                    │
     │                  │                 │                    │
┌────┴────┐      ┌──────┴─────┐    ┌─────┴──────┐    ┌───────┴──────┐
│         │      │            │    │            │    │              │
│ Celery  │      │   Kafka    │    │   Redis    │    │  PostgreSQL  │
│ Workers │      │  Streams   │    │   Cache    │    │ TimescaleDB  │
│         │      │            │    │            │    │              │
└─────────┘      └────────────┘    └────────────┘    └──────────────┘
     │
     │
┌────┴──────────────────────────────────────────────────────────────┐
│                    External Integrations                           │
│                                                                     │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ Shopify  │  │  Stripe   │  │ QuickBks │  │   Amazon     │    │
│  │   API    │  │    API    │  │   API    │  │  Seller API  │    │
│  └──────────┘  └───────────┘  └──────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Frontend (Next.js)

**Technology**: Next.js 14, React 18, TypeScript

**Responsibilities**:
- Server-side rendering for SEO and performance
- Real-time dashboard updates
- Responsive design for mobile and desktop
- State management with React Query

**Key Features**:
- Optimistic UI updates
- Progressive Web App (PWA) support
- Real-time notifications via WebSockets

### 2. API Layer (Django REST Framework)

**Technology**: Django 5.0, Django REST Framework

**Responsibilities**:
- RESTful API endpoints
- Authentication and authorization (JWT)
- Request validation and serialization
- Rate limiting and throttling

**Key Modules**:
- `accounts`: User and organization management
- `transactions`: Transaction processing and reconciliation
- `inventory`: Inventory and COGS tracking
- `integrations`: Platform connectors
- `ml`: Machine learning and anomaly detection
- `reporting`: Financial reports and dashboards
- `revenue_recognition`: ASC 606 compliance

### 3. Data Layer

#### PostgreSQL with TimescaleDB

**Purpose**: Primary relational database with time-series optimization

**Key Features**:
- ACID compliance for financial data
- TimescaleDB hypertables for transaction time-series
- Automatic data retention policies
- Continuous aggregates for reporting

**Tables**:
- Organizations, Users, Chart of Accounts
- Transactions, Fees, Journal Entries
- Inventory Items, Locations, Movements
- Integrations, Sync Logs
- Revenue Contracts, Schedules
- ML Anomalies, Forecasts

#### Redis

**Purpose**: Caching and session storage

**Use Cases**:
- API response caching
- Session management
- Celery message broker
- Real-time pub/sub

### 4. Message Queue (Kafka)

**Purpose**: Event streaming and real-time data processing

**Topics**:
- `nova-ledger-transactions`: Transaction events
- `nova-ledger-inventory`: Inventory updates
- `nova-ledger-reconciliation`: Reconciliation events

**Use Cases**:
- Webhook event processing
- Real-time sync from integrations
- Audit logging
- Event sourcing

### 5. Background Workers (Celery)

**Purpose**: Asynchronous task processing

**Task Types**:
- **Periodic Tasks** (Celery Beat):
  - Scheduled syncs from integrations
  - Daily financial report generation
  - Anomaly detection runs
  - Revenue recognition schedules

- **On-Demand Tasks**:
  - Transaction processing
  - Payout reconstruction
  - Large report generation
  - Bulk data imports

### 6. Machine Learning Layer

**Technology**: TensorFlow, scikit-learn

**Models**:
- **Anomaly Detection**: Detects unusual fees, amounts, patterns
- **Transaction Categorization**: Auto-categorizes transactions
- **Fraud Detection**: Flags suspicious activity
- **Financial Forecasting**: Predicts future revenue, cash flow

**Deployment**:
- Models served via TensorFlow Serving
- Periodic retraining pipeline
- A/B testing framework

## Data Flow

### Transaction Sync Flow

```
Shopify Order Created
        │
        ├─> Webhook received at /api/webhooks/shopify/
        │
        ├─> Webhook Event stored in DB
        │
        ├─> Published to Kafka topic: nova-ledger-transactions
        │
        ├─> Celery worker consumes message
        │
        ├─> Transaction created in DB
        │
        ├─> ML Anomaly Detection runs
        │
        ├─> Inventory adjusted
        │
        ├─> Journal Entry created
        │
        ├─> Sync to QuickBooks (if enabled)
        │
        └─> Dashboard metrics updated (cached in Redis)
```

### Payout Reconstruction Flow

```
Bank Transaction Detected
        │
        ├─> PayoutReconstructionService.reconstruct_payout()
        │
        ├─> Fetch all related transactions in date range
        │
        ├─> Calculate gross sales, fees, refunds
        │
        ├─> Verify payout amount matches calculation
        │
        ├─> Create balanced Journal Entry:
        │      DR Cash (Bank)
        │      DR Processing Fees Expense
        │         CR Sales Revenue
        │         CR Sales Tax Payable
        │
        ├─> Mark transactions as reconciled
        │
        └─> Generate reconciliation report
```

## Security Architecture

### Authentication & Authorization

- **JWT Tokens**: Stateless authentication
- **Refresh Tokens**: Long-lived with rotation
- **Role-Based Access Control (RBAC)**:
  - Owner: Full access
  - Admin: All features except billing
  - Accountant: Read/write financial data
  - Viewer: Read-only access

### Data Encryption

- **At Rest**: AES-256 encryption for sensitive fields
- **In Transit**: TLS 1.3 for all connections
- **Database**: Encrypted backups
- **API Keys**: Hashed and encrypted in database

### Compliance

- **SOC 2 Type 2**: Security, availability, confidentiality
- **GDPR**: Data privacy and right to deletion
- **CCPA**: California consumer privacy
- **PCI DSS**: Payment card data security (via Stripe)

## Scalability

### Horizontal Scaling

- **Frontend**: Multiple Next.js instances behind load balancer
- **API**: Stateless Django instances (auto-scaling)
- **Workers**: Celery workers scale based on queue depth
- **Database**: Read replicas for reporting queries

### Performance Optimization

- **Caching Strategy**:
  - Redis for frequently accessed data
  - CDN for static assets
  - Database query optimization with indexes

- **Database Partitioning**:
  - TimescaleDB automatic chunk management
  - Partition tables by organization_id
  - Archive old data to cold storage

### Monitoring

- **Application Monitoring**: Sentry
- **Infrastructure Monitoring**: Prometheus + Grafana
- **Log Aggregation**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Uptime Monitoring**: Pingdom

## Deployment Architecture

### Kubernetes Cluster

```yaml
Namespaces:
  - nova-ledger-prod
  - nova-ledger-staging

Deployments:
  - frontend (3 replicas)
  - api (5 replicas)
  - celery-worker (10 replicas)
  - celery-beat (1 replica)

Services:
  - frontend-service (LoadBalancer)
  - api-service (ClusterIP)
  - postgres-service (StatefulSet)
  - redis-service (StatefulSet)
  - kafka-service (StatefulSet)

Ingress:
  - NGINX Ingress Controller
  - SSL/TLS termination
  - Rate limiting
```

### CI/CD Pipeline

```
GitHub Push
    │
    ├─> GitHub Actions triggered
    │
    ├─> Run tests (pytest, jest)
    │
    ├─> Build Docker images
    │
    ├─> Push to Container Registry (AWS ECR)
    │
    ├─> Deploy to Staging (Kubernetes)
    │
    ├─> Run integration tests
    │
    ├─> Manual approval gate
    │
    └─> Deploy to Production (Blue/Green)
```

## Disaster Recovery

### Backup Strategy

- **Database**: Continuous backup with PITR (Point-in-Time Recovery)
- **Files**: S3 with versioning enabled
- **Configuration**: GitOps with IaC (Terraform)

### Recovery Time Objectives

- **RTO (Recovery Time Objective)**: < 1 hour
- **RPO (Recovery Point Objective)**: < 5 minutes

### High Availability

- **Multi-AZ Deployment**: Primary + standby in different availability zones
- **Automatic Failover**: Database and cache layers
- **Health Checks**: Kubernetes liveness and readiness probes

## Future Enhancements

1. **GraphQL API**: Alternative to REST for more flexible queries
2. **Real-time Collaboration**: WebSocket-based collaborative editing
3. **Mobile Apps**: Native iOS and Android applications
4. **Blockchain Integration**: Audit trail on blockchain
5. **Advanced AI**: GPT-powered financial assistant
