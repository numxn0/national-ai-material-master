# National Code Governance

National Material records now support lifecycle governance and revision history.

## Lifecycle States

- `ACTIVE`
- `UNDER_REVIEW`
- `DEPRECATED`
- `REPLACED`

## Governance APIs

- `GET /api/national-governance/materials/{code}/current`
- `GET /api/national-governance/materials/{code}/revisions`
- `POST /api/national-governance/materials/{code}/change-request`
- `POST /api/national-governance/materials/{code}/deprecate`

Changes to active national materials are recorded as revisions and audit events. Replacement references preserve mappings and historical audit context.
