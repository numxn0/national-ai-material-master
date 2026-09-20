# Legacy Migration Workbench

The legacy migration workbench imports historical CPSE material catalog files without weakening the current durable ingestion pipeline.

## Supported Files

- CSV
- Excel `.xlsx`

## Modes

- Dry-run validates, maps, detects duplicates, records a migration job, and stores rejected-row details without creating `SourceMaterial` rows.
- Import reuses durable ingestion, creates an ingestion batch, writes valid `SourceMaterial` rows, and stores rejected rows.
- Rollback deletes only unapproved source materials created by that migration job.

Rollback never deletes approved national materials, approved mappings, approval cases, or audit events.

## Protected APIs

- `POST /api/migration/legacy-materials`
- `GET /api/migration/jobs/{job_id}`
- `GET /api/migration/jobs/{job_id}/errors.csv`
- `POST /api/migration/jobs/{job_id}/rollback`

Actions require `ADMIN` or `CPSE_USER`; scoped CPSE users can act only within their organization scope.
