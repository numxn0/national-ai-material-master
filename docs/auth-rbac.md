# Local Basic Auth and RBAC

The backend now supports durable local users, multiple roles per user, HTTP Basic authentication, and server-enforced RBAC for production governance and audit APIs.

## Roles

- `ADMIN`: can perform production operations across organizations.
- `CPSE_USER`: can create ingestion/import/governance actions for its configured organization scope.
- `L1_REVIEWER`: can perform L1 approval decisions.
- `L2_AUTHORITY`: can perform L2 approval decisions.
- `AUDITOR`: can read and verify the persistent audit ledger.

## Local Bootstrap

Users are created only when explicitly bootstrapped. No default users are created at FastAPI startup.

Example:

```powershell
$env:NAMM_BOOTSTRAP_USERNAME = "local-admin"
$env:NAMM_BOOTSTRAP_PASSWORD = "<set-a-local-secret>"
$env:NAMM_BOOTSTRAP_DISPLAY_NAME = "Local Admin"
$env:NAMM_BOOTSTRAP_ROLES = "ADMIN,AUDITOR"
$env:NAMM_BOOTSTRAP_ORGANIZATION_SCOPE = ""
.\backend\.venv\Scripts\python.exe .\backend\seed_local_users.py
```

Plaintext passwords are never stored; the service stores an Argon2 password hash through `pwdlib`.

## Basic Auth Usage

Use HTTP Basic credentials when calling protected production endpoints:

```powershell
$pair = "local-admin:<set-a-local-secret>"
$token = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
Invoke-RestMethod `
  -Method Get `
  -Uri "http://localhost:8000/api/auth/me" `
  -Headers @{ Authorization = "Basic $token" }
```

`GET /api/auth/me` returns username, display name, organization scope, and roles. It never returns password hashes or password material.

## Protected Endpoint Matrix

| Endpoint area | Required roles |
| --- | --- |
| `POST /api/materials/ingest-csv` | `ADMIN`, `CPSE_USER` |
| `POST /api/matching/run/{batch_id}` | `ADMIN`, `CPSE_USER` |
| `POST /api/national-materials/draft-from-candidate/{candidate_id}` | `ADMIN`, `CPSE_USER` |
| `GET /api/mappings/source/{source_material_id}` | `ADMIN`, `CPSE_USER` |
| `POST /api/approvals/cases/from-national-material/{code}` | `ADMIN`, `CPSE_USER` |
| `GET /api/approvals/cases*` | `ADMIN`, `L1_REVIEWER`, `L2_AUTHORITY`, `AUDITOR` |
| L1 approval decisions | `ADMIN`, `L1_REVIEWER` |
| L2 approval decisions | `ADMIN`, `L2_AUTHORITY` |
| Approval resubmission | `ADMIN`, `CPSE_USER`, `L1_REVIEWER` |
| `GET /api/audit/events` and `POST /api/audit/verify` | `ADMIN`, `AUDITOR` |
| `POST /api/integrations/sap/import-materials` | `ADMIN`, `CPSE_USER` |
| `GET /api/integrations/import-runs/{id}` | `ADMIN`, `CPSE_USER`, `AUDITOR` |

Demo endpoints, health endpoints, preview endpoints, and placeholder presentation routes remain unauthenticated for compatibility.

## Organization Scope

`CPSE_USER` accounts can include an optional `organization_scope`. When configured, production ingestion and SAP import requests must declare the same CPSE organization. `ADMIN` can act across organizations.

Row-level read filtering and SSO-backed organization claims are future work.

## Limitations

- HTTP Basic is a local milestone, not the final identity architecture.
- No SSO/SAML/OAuth, MFA, password reset, account lifecycle UI, or rate limiting yet.
- No production credential vault or secret rotation integration yet.
- No row-level permissions beyond the current CPSE write-scope checks.
