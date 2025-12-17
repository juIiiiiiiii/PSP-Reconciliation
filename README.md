# PSP Reconciliation Platform

Production-grade Payment Service Provider (PSP) Reconciliation Platform for iGaming operators.

## Architecture

This platform reconciles millions of transactions monthly across multiple operators, brands, entities, jurisdictions, and currencies. It handles deposits, withdrawals, refunds, chargebacks, fees, reserves, and FX conversions from diverse sources (APIs, webhooks, settlement files) with near-real-time exception detection and daily settlement reconciliation.

## Technology Stack

- **Cloud**: AWS (multi-AZ, multi-region)
- **Event Bus**: Amazon Kinesis Data Streams (with DynamoDB for exactly-once)
- **Databases**: PostgreSQL 15+ (primary), Amazon S3 (raw data lake)
- **Compute**: AWS ECS Fargate (containers), AWS Lambda (event-driven)
- **Cache**: Amazon ElastiCache (Redis)
- **Monitoring**: CloudWatch, Datadog, PagerDuty
- **SSO**: AWS SSO / Okta integration

## Project Structure

```
.
├── backend/
│   ├── services/
│   │   ├── ingestion/          # Webhook, API, file ingestion
│   │   ├── normalization/     # Event normalization and parsing
│   │   ├── reconciliation/    # Matching engine
│   │   ├── ledger/            # Double-entry accounting
│   │   ├── chargeback/        # Chargeback lifecycle
│   │   ├── reporting/         # Analytics and reports
│   │   └── api/               # REST API with RBAC
│   ├── shared/
│   │   ├── models/            # Data models
│   │   ├── database/          # DB schemas and migrations
│   │   └── utils/             # Shared utilities
│   └── infrastructure/        # Terraform/IaC
├── frontend/                  # React/TypeScript UI
├── database/
│   ├── migrations/           # Alembic/Flyway migrations
│   └── seeds/                # Seed data
└── docs/                     # Documentation
```

## Getting Started

See individual service READMEs for setup instructions.

## License

Proprietary


