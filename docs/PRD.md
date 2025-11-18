# Nova Ledger: Product Requirements Document

## 1. Product Overview and Vision

| Field | Description |
|-------|-------------|
| **Product Name** | Nova Ledger |
| **Product Goal** | To be the most accurate, compliant, and intelligent accounting automation layer for high-growth, multi-channel e-commerce and SaaS businesses. |
| **Vision** | To replace manual accounting labor and complex spreadsheet work with a single, AI-powered source of truth that delivers real-time profitability insights down to the SKU and customer level. |
| **Mission** | Provide precise, automated syncing and advanced financial modeling necessary for scaling businesses to make data-driven decisions confidently. |

## 2. Target Market and Customer Profile

| Field | Description |
|-------|-------------|
| **Primary ICP** | Multi-Channel E-commerce/Retail Brands: Businesses with $500K - $20M in annual revenue that sell across 3 or more channels (e.g., Shopify, Amazon, physical retail POS) and struggle to accurately track Cost of Goods Sold (COGS), inventory valuation, and channel profitability. |
| **Secondary ICP** | Scaling SaaS Companies: Companies with subscription models seeking advanced, real-time metrics beyond basic GAAP recognition, such as Customer Lifetime Value (CLV) by acquisition channel and detailed churn analysis. |
| **Key Pain Points** | 1. Inaccurate or delayed COGS calculation<br>2. Difficulty reconciling gross payouts from payment processors (Stripe, PayPal) with underlying sales, fees, and taxes<br>3. Lack of real-time, consolidated financial performance by sales channel/platform |
| **Target User Roles** | CFOs, Controllers, Internal Accountants, and specialized E-commerce Bookkeepers |

## 3. Competitive Analysis (vs. Synder)

| Feature Area | Synder's Position | Nova Ledger's Competitive Edge |
|--------------|-------------------|--------------------------------|
| **Core Sync** | Transaction-level sync of sales, fees, and taxes. Strong focus on accuracy and reconciliation. | **Parity + Hyper-Detail**: Same high-accuracy sync, but with granular tracking of every single fee layer (e.g., Stripe processing, dispute fees, foreign exchange fees) mapped to separate ledger accounts for maximum visibility. |
| **Inventory/COGS** | Basic sync, often relying on the e-commerce platform's data. | **Advanced Perpetual Inventory**: Dedicated module for calculating Moving Average Cost (MAC) and syncing it to the ledger at the moment of sale. Includes support for landed costs (freight, duty, insurance) amortization. |
| **Revenue Recognition** | Synder RevRec: Strong, GAAP-compliant, automated deferred revenue schedules (ASC 606). | **Parity + Scenario Modeling**: Includes GAAP-compliant RevRec, but adds a Forecasting Module for projecting deferred revenue and future cash flow based on adjustable growth and churn assumptions. |
| **Financial Reporting** | Synder Insights: Plug-n-play business analytics, multi-channel dashboard. | **Intelligent Channel P&Ls**: Automatically generates a detailed, accurate Profit & Loss statement per sales channel (Amazon, Shopify, etc.) by correctly allocating fees and COGS, allowing for instant identification of the most/least profitable channels. |
| **Differentiator** | AI-driven transaction categorization and high-volume processing. | **AI-Driven Financial Intelligence**: Utilizes Machine Learning for outlier detection in transaction data, flagging potential accounting errors, mismatched fees, or fraud attempts before reconciliation. |

## 4. Key Features and Functionality

### 4.1. Core Sync & Reconciliation (MVP)

- **Multi-Platform Connectivity**: Seamless, secure, and bidirectional integration with:
  - **Accounting/ERP**: QuickBooks Online/Desktop, Xero, NetSuite, Sage Intacct
  - **Sales**: Shopify (Plus), Amazon Seller Central, Stripe, PayPal, Square, WooCommerce

- **"Gross Payout" Reconstruction**: Automatically breaks down every bank deposit/payout into its constituent parts:
  - Sales Revenue
  - Sales Tax Collected
  - Payment Processing Fees
  - Platform Fees (e.g., Amazon FBA fees)
  - Refunds

- **Tax Engine**: Automated calculation and mapping of sales tax liabilities based on origin, destination, and product tax codes, supporting nexus tracking.

### 4.2. Advanced Inventory & COGS Module (Key Differentiator)

- **Landed Cost Allocation**: Tools to input or integrate freight, customs, and inspection costs, and automatically allocate them to SKUs to calculate a true, comprehensive Cost of Goods Sold.

- **Perpetual Inventory Sync**: Real-time synchronization of inventory movement and valuation from the e-commerce platform into the accounting system (eliminating the need for separate inventory-only tools).

- **Warehouse/Fulfillment Support**: Detailed tracking of inventory across multiple locations (e.g., 3PL, FBA, internal warehouse) and correct COGS calculation regardless of where the item shipped from.

### 4.3. Financial Intelligence & Reporting

- **Profitability Dashboard**: Single-screen view of Net Profit, Gross Margin, and ROI, segmented by:
  - Sales Channel
  - Product Category / SKU
  - Customer Cohort

- **Advanced SaaS Metrics** (for SaaS customers): Automated calculation of Monthly Recurring Revenue (MRR), Annual Recurring Revenue (ARR), Customer Acquisition Cost (CAC), and LTV.

- **Error Detection AI**: Machine learning model trained to spot reconciliation anomalies (e.g., a fee percentage far exceeding the standard rate) and generate an actionable alert for the accounting team.

## 5. Technical Architecture

| Component | Technology / Stack | Rationale |
|-----------|-------------------|-----------|
| **Frontend** | React/Next.js | Fast, modern, scalable user interface for a powerful web application. |
| **Backend** | Python (Django/Flask) or Go (Golang) | High performance and concurrency needed for processing massive volumes of financial transactions (Python is excellent for ML/AI components). |
| **Database** | PostgreSQL/TimescaleDB | Robust relational database; TimescaleDB for efficient storage and querying of time-series transaction data. |
| **Data Processing** | Apache Kafka / AWS Kinesis | Real-time stream processing for handling high-volume transaction webhooks from platforms like Stripe and Shopify. |
| **Security/Compliance** | SOC 2 Type 2 Certified, GDPR/CCPA readiness, AES-256 Encryption at rest and in transit. | Non-negotiable enterprise-grade security to handle sensitive financial data. |
| **AI/ML** | AWS SageMaker / TensorFlow | For automated categorization, error detection, and financial forecasting models. |

## 6. Go-to-Market Strategy

| Field | Description |
|-------|-------------|
| **Pricing Model** | Tiered Model based on Monthly Transaction Volume and Feature Set |
| **Tiers** | 1. **Growth**: (Up to 5k transactions/month): Core Sync & Reconciliation<br>2. **Pro**: (Up to 25k transactions/month): Growth features + Full COGS/Inventory Module<br>3. **Enterprise**: (Unlimited volume): Pro features + Financial Intelligence/Forecasting |
| **Sales Channels** | Primary: Direct Sales focused on mid-market e-commerce/SaaS<br>Secondary: Strong focus on the Accountant/Bookkeeper Partner Program |
| **Marketing Focus** | Content marketing centered on solving advanced accounting problems |
| **Initial MVP Launch** | Focus exclusively on the Shopify + QuickBooks Online + Advanced COGS integration |

## 7. Success Metrics (KPIs)

| Metric | Target |
|--------|--------|
| **ARR (Annual Recurring Revenue)** | $1M within 12 months |
| **Customer LTV:CAC Ratio** | Minimum 3:1 |
| **Partner Adoption** | 50 Certified Accounting Firms within 6 months |
| **Data Accuracy Score** | 99.99% match rate between reconciled data and bank deposits |
| **Customer Churn (Logo)** | Below 5% annually |
