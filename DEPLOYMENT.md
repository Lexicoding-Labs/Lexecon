# Deployment Guide

## Required GitHub Secrets

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM access key for ECR push and EKS deploy |
| `AWS_SECRET_ACCESS_KEY` | IAM secret key |
| `AWS_REGION` | AWS region (e.g. `us-east-1`) |
| `DATABASE_URL_STAGING` | Postgres connection string for staging |
| `DATABASE_URL_PRODUCTION` | Postgres connection string for production |
| `SLACK_WEBHOOK` | Slack incoming webhook for deploy notifications |
| `TERRAFORM_STATE_BUCKET` | S3 bucket for Terraform state (infra workflow only) |
| `TERRAFORM_LOCK_TABLE` | DynamoDB table for Terraform locking (infra workflow only) |

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

## Local Development

```bash
# Install Python deps
pip install -e ".[dev]"

# Start API server (port 8000)
python -m uvicorn lexecon.api.server:app --reload

# Start React frontend (port 3000, proxies to API)
cd frontend && npm install && npm start
```

Or build and run the full Docker image:

```bash
docker build -t lexecon:dev .
docker run --rm -p 8000:8000 lexecon:dev
# API at :8000/api/routes, frontend at :8000/
```

## Production Deploy

Deployments are triggered by GitHub Actions workflows:

- **Staging**: Push to `develop` triggers `.github/workflows/deploy-staging.yml`
- **Production**: Push to `main` triggers `.github/workflows/deploy-production.yml`
- **Docker image**: Push to `main`/`develop` triggers `.github/workflows/build.yml`

Manual deploy via script:

```bash
export DATABASE_URL="postgres://..."
./infrastructure/scripts/deploy.sh staging 1.0.0
./infrastructure/scripts/deploy.sh production 1.0.0
```

## Database Migrations

Migrations live in `migrations/` as numbered Python scripts. The runner (`migrations/run_all.py`) tracks applied migrations in a `schema_migrations` table.

```bash
# Run all pending migrations
python migrations/run_all.py [db_path]

# Default db_path: lexecon_auth.db (or LEXECON_DB_PATH env var)
```

Migrations run automatically during `deploy.sh` (before and after Helm deploy). They are idempotent — safe to run multiple times.

## Rollback

```bash
./infrastructure/scripts/rollback.sh <environment>
# Example: ./infrastructure/scripts/rollback.sh production
```

## Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe — returns `{"status": "healthy"}` |
| `GET /status` | Readiness probe — includes policy engine state and uptime |
| `GET /metrics` | Prometheus-format metrics |
| `GET /api/routes` | List all available API endpoints |
