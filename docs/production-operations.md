# Production Operations

This project is production-ready for local demonstration and verification, not nationwide cloud operation.

## Local SQLite Demo

```powershell
.\backend\.venv\Scripts\python.exe .\backend\run_production_demo.py --database-url "sqlite:///backend/data/production_demo.db" --fresh
```

## PostgreSQL Target

Set `DATABASE_URL` to a PostgreSQL-compatible SQLAlchemy URL before running Alembic migrations or the app. Do not use `--fresh` for PostgreSQL; destructive reset is intentionally refused.

## Docker Environment

Use `.env` or container environment variables for:

- `DATABASE_URL`
- `CORS_ORIGINS`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_ALLOW_STUB_FALLBACK`
- `SAP_ODATA_MODE`
- `SAP_ODATA_ENTITY_SET`

Secrets such as SAP passwords and bearer tokens must come from an external secret manager or container secret injection. The app does not persist SAP passwords, bearer tokens, or raw authorization headers.

## Still Pending For Nationwide Production

- cloud deployment
- SSO/OAuth/SAML/MFA
- credential vault integration
- certified live SAP connectivity
- pgvector tuning and ANN indexes
- background workers for large imports
- observability, backups, restore drills, and incident runbooks
