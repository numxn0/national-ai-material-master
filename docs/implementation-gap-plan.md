# National AI Material Master Production-Readiness Checklist

Date: 2026-09-20

This document captures the current implementation state after inspecting the repository and running the backend/frontend verification paths. The project now has a durable local production demonstration path covering ingestion, matching, national-code drafting, L1/L2 governance, audit, analytics, mock SAP import, and Basic Auth/RBAC. Production deployment, external identity, real SAP connectivity, large-scale vector search, trained ML, and operations hardening remain pending.

## Verification Snapshot

| Area | Command Used | Result |
| --- | --- | --- |
| Backend verification scripts | `$scripts = Get-ChildItem .\backend -Filter 'verify*.py' \| Sort-Object Name; foreach ($script in $scripts) { Write-Host "=== $($script.Name) ==="; .\backend\.venv\Scripts\python.exe $script.FullName; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }` | PASS after Prompt 12. All backend verification scripts, including `verify_prompt12.py`, passed. |
| Frontend build, first attempt | `& 'C:\Users\Asus\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' run build` | FAIL before TypeScript/Vite build. Local pnpm blocked `esbuild@0.21.5` postinstall with `ERR_PNPM_IGNORED_BUILDS`. |
| Frontend build, retry after local build approval | `& 'C:\Users\Asus\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' approve-builds --all; & 'C:\Users\Asus\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' run build` | PASS. `tsc -b && vite build` completed; Vite generated production assets successfully. |

## Implemented Features

- FastAPI backend with health, materials, matching, approvals, audit, and demo summary routers.
- Typed Pydantic schemas for source materials, national materials, mappings, matching candidates, embeddings, hybrid scores, explanations, approvals, audit events, and demo telemetry.
- CSV ingestion preview for the bundled sample dataset and uploaded CSV files, including header mapping, validation summaries, normalized source material records, and no-persistence disclosure.
- Durable CSV ingestion endpoint for multipart CSV uploads, backed by SQLAlchemy ingestion batches, persisted source materials, idempotent file replay, duplicate-row rejection, and persisted ingestion row errors.
- Rule-based normalization for punctuation, UOMs, categories, tokenization, and standard material descriptions.
- Rule-based attribute extraction for key industrial domains including bearings, pipes, valves, cables, motors, and fasteners.
- RapidFuzz candidate duplicate detection with domain blocking, similarity scoring, critical attribute conflict handling, and ranked candidate output.
- Persisted rule-based matching for durable ingestion batches, including database-backed candidate generation, hybrid scoring, explainability storage, idempotent candidate upsert, and saved result retrieval.
- Durable DRAFT national material code recommendation from persisted match candidates, with deterministic `NAMM-{CATEGORY}-{SUBCATEGORY}-{FINGERPRINT}` codes and source-material mappings.
- Durable L1/L2 approval case workflow for DRAFT national materials, including persisted reviewer decisions, valid state transitions, approval-controlled publication to ACTIVE, and source mapping status updates.
- Durable append-only audit ledger for production workflows, with persisted sequence numbers, SHA-256 hash chaining, chain-state tip tracking, and replay verification endpoints.
- Pluggable semantic embedding providers with durable vector storage: deterministic local stub by default, optional lazy-loaded `sentence-transformers` provider via `backend/requirements-ai.txt`, explicit fallback metadata, and persisted source-material embedding comparison.
- SAP OData integration interface with mock and live connector implementations, durable import-run tracking, idempotent mock imports, sanitized configuration handling, and reuse of the durable source-material ingestion pipeline.
- Local HTTP Basic authentication with durable users, many-to-many roles, Argon2 password hashes, server-enforced RBAC on production governance/audit/import endpoints, and authenticated approval actor identity.
- Reproducible safe production demo runner that applies migrations to an explicit database URL, seeds local role users, runs the authenticated durable workflow from CSV/SAP ingestion through ACTIVE national material publication, verifies the audit chain, and prints a sanitized JSON summary.
- Durable taxonomy/specification governance with seeded industrial domains, versioned attribute definitions, lifecycle status, validation APIs, and audit events.
- Legacy migration workbench for CSV/XLSX dry-run/import/error reporting/safe rollback, reusing durable ingestion.
- Historical procurement-history import with actual-spend analytics separated from estimated savings.
- ML-ready label export, model-run metadata, optional ML dependency path, explicit insufficient-label refusal, and rule-baseline fallback.
- National-code lifecycle governance with revision history, change requests, deprecation, replacement references, and audit events.
- Lightweight production frontend login/session handling, authenticated production workflows, and demo mode preservation.
- GitHub Actions CI workflow for backend verification, frontend build, and basic dependency audit.
- Rule-based hybrid match scoring with transparent weighted signals, conflict caps, classifications, and ML feature export rows.
- Deterministic SHAP-style explainability with factor contributions, reviewer summaries, driver/risk lists, and audit-oriented explanation records.
- Demo dual-tier approval workflow with proposed NAMM codes, L1/L2 state simulation, procurement impact estimates, and mapping previews.
- Demo SHA-256 audit trail generator and verifier with chained event hashes and tamper-detection checks.
- React/Vite frontend with upload, matching review, approvals, and audit views connected to demo/production-compatible APIs, plus a dashboard now wired to live persisted analytics.
- Database-backed production analytics summary API for durable ingestion, matching, approval, national-code, audit-chain, CPSE/category breakdown, recent activity, and ingestion timeline metrics.
- Dockerfiles and `docker-compose.yml` for local multi-container demo execution.
- Documentation covering architecture, canonical schema, database target schema, demo script, and walkthrough.
- SQLAlchemy 2.x database foundation with SQLite local default, PostgreSQL-compatible `DATABASE_URL`, ORM models, Alembic configuration, and initial migration revision `0001_database_foundation`.

## Partial Features

- Material catalog endpoints such as `GET /api/materials`, `GET /api/materials/{id}`, and `POST /api/materials/upload` still use placeholder in-memory records or queued-response stubs.
- Matching queue, trigger, and decision endpoints include legacy placeholder data; durable batch matching now exists, but asynchronous production jobs and reviewer decision persistence are still pending.
- Approval endpoints now include a durable production case workflow; demo queue/action routes remain simulated for compatibility.
- Audit trail logic now includes both generated demo chains and a persistent production ledger with hash-chain verification. External timestamping/signing, retention/export policy, SIEM integration, and compliance export packages remain pending.
- Semantic embeddings are persisted through a provider interface. The active default remains deterministic feature hashing; real sentence-transformer generation is configuration-gated and optional.
- ML training is structurally ready and guarded, but real trained-model operation requires enough labelled decisions, optional ML dependencies, and explicit local training enablement.
- ML feature export and training-plan endpoints exist, but labels are null and no trained XGBoost/LightGBM model is loaded.
- SHAP-style explanations are deterministic factor decompositions, not TreeSHAP outputs from a trained model.
- Database schema documentation now has an implemented SQLAlchemy/Alembic foundation behind it, plus durable CSV ingestion, mock SAP OData import-run tracking, persisted rule-based matching, and draft national-code mapping paths. Many production API persistence paths are still pending.
- Frontend dashboard uses persisted production analytics without demo fallback numbers. Other frontend views still use demo/sample endpoints or offline/mock fallback behavior and are not yet wired to authenticated production workflows.
- Verification is script-based and strong for demo flows, but not yet organized as CI test suites with coverage thresholds.

## Demo-Only, In-Memory, Or Stub Modules

- `backend/app/services/embedding_service.py`: legacy deterministic token-hash demo endpoints remain. `backend/app/services/persistent_embeddings.py` adds durable provider-backed embedding storage; pgvector ANN search remains pending.
- `backend/app/services/approval_workflow.py`: non-persisted approval queue and L1/L2 workflow simulation generated from sample CSV data.
- `backend/app/services/audit_trail.py`: non-persisted demo audit chain generated in memory.
- `backend/app/api/demo.py`: reports `persistence_status="demo_in_memory_only"` and `is_database_connected=False`.
- `backend/app/api/materials.py`: placeholder material catalog/list/detail/upload endpoints alongside working preview/normalization/extraction endpoints.
- `backend/app/api/matching.py`: durable run/results endpoints now use persisted source materials and match candidates; legacy placeholder queue/action endpoints and sample/demo endpoints remain for compatibility.
- `backend/app/api/approvals.py`: durable `/cases/*` endpoints are production-backed; demo action processing still returns `persisted=False`, and legacy endpoints return placeholder approval records.
- `frontend/src/services/api.ts`: dashboard analytics call is production-backed and fails visibly on API errors. Other UI services remain primarily wired to demo/sample endpoints and include offline/mock fallback response paths.

## Missing Production Features

- Persistent storage: SQLAlchemy models, SQLite local database configuration, Alembic migrations through `0009_ps_completion_foundations`, durable ingestion/matching/governance/audit/procurement/taxonomy foundations are implemented; backup/restore testing and environment promotion remain pending.
- Vector search: durable JSON vector storage and pluggable stub/sentence-transformer generation are implemented. pgvector extension setup, HNSW/IVFFlat indexes, vector refresh jobs, model registry, and candidate retrieval at scale remain pending.
- Real ML pipeline: labeled reviewer dataset, model training/evaluation, model registry, versioned model loading, confidence calibration, drift checks, and TreeSHAP explanations.
- Durable ingestion: CSV upload persists ingestion batches, source materials, row-level errors, and idempotent file replays. Legacy migration supports CSV/XLSX dry-run/import/error reports/safe rollback. SAP OData has a connector abstraction, mock import path, live preflight validation, sync-ready configuration records, and durable import-run tracking. Certified SAP deployment, scheduled job execution, SAP IDoc/BAPI support, non-SAP ERP connectors, object storage, and large-file background processing remain pending.
- Governance workflow: draft national-code recommendation, PENDING_L1 source mappings, durable L1/L2 state transitions, reviewer notes, authenticated RBAC, and approval-controlled publication to ACTIVE are implemented. Assignment queues, escalation paths, notifications, SLA tracking, and unpublish flows remain pending.
- Security: local Basic Auth, durable users/roles, CPSE write-scope checks, configured CORS origins, and authenticated production approval/audit actor identity are implemented. SSO/SAML/OAuth integration, MFA, password reset, account lifecycle management, row-level read permissions, production secret management, CSRF hardening, rate limits, and input abuse controls remain pending.
- ERP credential operations: SAP OData responses are sanitized and local verification avoids real credentials. Production credential vaulting, secret rotation, certified SAP connectivity review, and organization-scoped connector permissions remain pending.
- Audit and compliance: append-only audit storage, durable hash-chain tip management, and tamper-evidence over persisted production records are implemented. External timestamping/signing strategy, export retention rules, SIEM integration, and compliance reports remain pending.
- API hardening: pagination standards, idempotency keys, structured error contracts, request size limits, background jobs, OpenAPI examples for production endpoints, and compatibility/versioning policy.
- Frontend production readiness: the dashboard now has live persisted analytics and actual procurement metrics; the app has in-memory Basic Auth login/logout and authenticated production workflow panels for upload, migration, matching, approvals, and audit. Deeper role-specific navigation, pagination/filtering across all pages, accessibility pass, and removal of all remaining demo fallback assumptions remain pending.
- Observability and operations: structured logs, metrics, traces, health/readiness probes, SLO dashboards, alerting, deployment runbooks, and incident/debug tooling.
- CI/CD and quality gates: automated backend tests, frontend build, linting, type checks, security scanning, dependency audits, Docker image builds, and migration checks on every pull request.
- Performance and scale: blocking strategy validation on large catalogs, database indexing, candidate-generation benchmarks, async task queues, cache strategy, and load testing.

## Recommended Build Order

1. Preserve the demo baseline in CI.
   - Convert the existing verification scripts into automated CI jobs.
   - Add frontend build verification and fail fast on TypeScript errors.
   - Keep sample-data demo tests as regression fixtures while production modules are introduced.

2. Add the persistence foundation.
   - Implemented in Prompt 2: SQLAlchemy models and an initial SQLite-compatible, PostgreSQL-oriented Alembic migration for source materials, national materials, mappings, ingestion batches, candidate pairs, approval cases, and audit events.
   - Add a repository/service layer so API routes stop depending on placeholder arrays or sample CSV reads.
   - Add environment configuration for local, staging, and production databases.

3. Make ingestion durable.
   - Implemented in Prompt 3: `POST /api/materials/ingest-csv` persists CSV ingestion batches and valid source materials while keeping `POST /api/materials/preview-csv` non-persistent.
   - Implemented in Prompt 3: parser-invalid rows, duplicate source codes, and replay-safe file idempotency are stored through durable batch and row-error records.
   - Store validation errors, normalized descriptions, extracted attributes, and source file metadata.
   - Pending: Excel import, ERP import, object storage, background jobs, and large-file processing.

4. Replace semantic stubs with pgvector search.
   - Implemented in Prompt 8: add provider selection, deterministic model metadata, optional `sentence-transformers` support through `backend/requirements-ai.txt`, and explicit fallback reporting.
   - Implemented in Prompt 8: generate/store embeddings for persisted source and national materials using SQLite/PostgreSQL-compatible JSON vectors.
   - Pending: pgvector-native columns, HNSW/IVFFlat indexes, ANN retrieval before RapidFuzz/hybrid re-ranking, refresh jobs, and model registry.

5. Productionize matching and scoring.
   - Implemented in Prompt 4: persist candidate pairs, feature vectors, hybrid scores, conflict explanations, explainability output, method versions, and idempotent upserts for durable batches.
   - Add async batch jobs for candidate generation and rescoring.
   - Keep current rule-based scoring as the audited baseline while collecting labels.

6. Build durable governance.
   - Implemented in Prompt 5: create DRAFT NationalMaterial records and PENDING_L1 source mappings from persisted MatchCandidate rows.
   - Implemented in Prompt 6: persist L1/L2 approval states, declared reviewer roles, comments, and transitions.
   - Implemented in Prompt 6: publish approved national codes by moving DRAFT NationalMaterial records to ACTIVE and source mappings to APPROVED.
   - Pending: authenticate reviewer identity, enforce real RBAC, add assignment queues, notifications, SLA escalation, and unpublish flows.

7. Upgrade audit trail to production ledger.
   - Implemented in Prompt 7: store ingestion, matching, draft creation, approval case, approval decision, resubmission, mapping-status, and publication events in append-only audit tables.
   - Implemented in Prompt 7: chain SHA-256 hashes across persisted events, maintain a durable latest chain tip, and verify the chain by replay.
   - Pending: export packages, external timestamping/signing, retention policy, SIEM integration, and authenticated actor identity.

8. Wire production analytics and operational reporting.
   - Implemented in Prompt 9: expose persisted analytics summary metrics, CPSE/category breakdowns, recent audit activity, ingestion timelines, audit-chain metadata, and a live React dashboard.
   - Pending: role-scoped analytics, richer filters, exports, SLA dashboards, forecasting, and performance reporting over large production datasets.

9. Add ERP integration foundations.
   - Implemented in Prompt 10: SAP OData connector protocol, mock connector fixture, live connector configuration validation, durable import runs, idempotent mock imports, and shared durable ingestion reuse.
   - Pending: certified SAP deployment, production credential vault, SSO-bound connector permissions, scheduled sync, change-data-capture, SAP IDoc/BAPI support, and additional ERP connectors.

10. Add authentication and authorization.
   - Implemented in Prompt 11: local durable users, multi-role assignments, Argon2 password hashes, HTTP Basic dependencies, production RBAC enforcement, CPSE write-scope checks, and authenticated actor identity for production approval decisions.
   - Pending: SSO/SAML/OAuth, MFA, password reset, account lifecycle workflows, row-level read filtering, production secret management, rate limiting, and frontend login/role-aware navigation.

11. Add reproducible production demo verification.
   - Implemented in Prompt 12: `backend/run_production_demo.py` applies migrations to an explicit database URL, safely recreates only allowed SQLite demo files with `--fresh`, seeds local role users, exercises the durable authenticated workflow, verifies audit/analytics output, and prints a sanitized final JSON summary.
   - Implemented in Prompt 12: `backend/verify_prompt12.py` runs the demo in a temporary SQLite database and validates safe rejection paths for unsafe SQLite and PostgreSQL `--fresh` targets.
   - Pending: convert the script suite into CI/CD jobs with published artifacts and environment promotion gates.

12. Close final PS completion foundations.
   - Implemented in final PS phase: governed taxonomy/specification models and APIs, legacy migration workbench, procurement history import/analytics, ML-ready metadata and guarded training path, SAP live preflight and sync configuration records, national-code lifecycle governance, frontend production login/workflow panels, documentation, and CI workflow.
   - Pending: external credential vault, real SAP credentials/connectivity, nationwide-scale PostgreSQL/pgvector tuning, labelled production ML dataset, trained model promotion, and SSO.

13. Train and integrate supervised ML.
   - Use persisted reviewer decisions as labels.
   - Train/evaluate XGBoost or LightGBM, calibrate thresholds, and add TreeSHAP explanations.
   - Version models and compare them against the rule-based baseline before replacing default decisions.

14. Harden deployment and operations.
    - Add production Docker images, CI/CD, environment promotion, migration gates, observability, load testing, backups, and operational runbooks.
    - Run a security review before any production data onboarding.

## Production Readiness Checklist

- [ ] Backend verification scripts run in CI.
- [ ] Frontend `tsc -b && vite build` runs in CI.
- [x] Initial SQLAlchemy models and Alembic migration exist and can be applied from a clean local SQLite database.
- [ ] Production PostgreSQL/Supabase migration rollout and environment promotion are validated.
- [ ] No production endpoint depends on sample CSV files for primary behavior.
- [x] Durable production approval decisions are persisted; demo approval action routes still explicitly return `persisted=false` for compatibility.
- [x] CSV upload creates durable ingestion batches with validation status.
- [x] SAP OData mock import path creates durable import runs, ingestion batches, and source materials.
- [ ] Certified live SAP deployment, Excel/non-SAP ERP ingestion, scheduled sync, and large-file background processing are implemented.
- [x] Rule-based candidate generation can persist and idempotently upsert candidates for an ingestion batch.
- [ ] Candidate generation jobs are asynchronous, restartable, and production-scale.
- [x] Embeddings can be generated through a pluggable provider and stored durably as JSON vectors.
- [ ] Embeddings are stored in pgvector with ANN indexes and large-scale vector retrieval.
- [ ] Matching results store scoring method/version and all feature values.
- [x] Approval workflow validates declared L1/L2 reviewer roles and enforces valid state transitions.
- [x] DRAFT national-code recommendation and source-code mapping foundation are durable.
- [x] Approval-controlled publishing and declared-role L1/L2 review are implemented.
- [x] Audit events are append-only, persisted, chained, and independently verifiable through the production audit ledger.
- [x] Dashboard analytics summary is backed by persisted production tables instead of demo fallback numbers.
- [x] Local Basic Auth, durable roles, production RBAC, and CPSE write-scope checks protect sensitive production routes.
- [x] Reproducible safe end-to-end production demo verification runs from clean SQLite database to approved ACTIVE Common National Material Code.
- [x] Taxonomy/specification governance foundations are durable, seeded, versioned, and audited.
- [x] Legacy CSV/XLSX migration dry-run/import/error-report/safe-rollback workflow is implemented.
- [x] Procurement-history import and actual-spend analytics are implemented.
- [x] ML-ready labels/model-run metadata and insufficient-label refusal are implemented without fabricating training results.
- [x] SAP live readiness preflight and sync-ready configuration records are implemented without persisting secrets.
- [x] National-code lifecycle revision/deprecation/replacement governance is implemented.
- [x] Local frontend Basic Auth and authenticated production workflow panels are implemented.
- [x] GitHub Actions CI workflow is present for backend verification, frontend build, and basic dependency audit.
- [ ] SSO/SAML/OAuth, MFA, account lifecycle, row-level read permissions, and production identity operations are implemented.
- [ ] Frontend is role-aware and remaining non-dashboard pages do not rely on mock fallback data in production.
- [ ] Production deployment, CI/CD gates, external secret vaulting, production PostgreSQL/pgvector tuning, certified SAP connectivity, large-scale async jobs, and real supervised ML training are implemented.
- [ ] Structured logs, metrics, traces, alerts, and health/readiness probes are deployed.
- [ ] Dependency, container, and secret scanning run before release.
- [ ] Backup, restore, and disaster-recovery procedures are tested.
