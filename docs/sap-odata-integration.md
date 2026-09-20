# SAP OData Integration

The backend now includes a durable SAP OData connector interface that can test a connection and import material records into the same `IngestionBatch` and `SourceMaterial` tables used by CSV ingestion.

## Mock Mode

Mock mode is the default:

```powershell
$env:SAP_ODATA_MODE = "mock"
.\backend\.venv\Scripts\python.exe .\backend\verify_prompt10.py
```

Mock mode reads `backend/sample-data/sap_odata_materials_mock.json` and never calls external network services.

Useful endpoints:

```http
POST /api/integrations/sap/test-connection
POST /api/integrations/sap/import-materials
GET /api/integrations/import-runs/{import_run_id}
```

Example import body:

```json
{
  "source_cpse": "BHEL",
  "source_system": "SAP_ECC_BHEL",
  "connection_name": "bhel-sap-mock",
  "entity_set": "A_Material",
  "max_records": 100,
  "idempotency_key": "bhel-a-material-2026-09-20"
}
```

## Live Configuration

Live mode is configuration-gated:

```text
SAP_ODATA_MODE=live
SAP_ODATA_BASE_URL=https://sap.example.gov.in/sap/opu/odata/sap/API_PRODUCT_SRV
SAP_ODATA_ENTITY_SET=A_Material
SAP_ODATA_TIMEOUT_SECONDS=10
SAP_ODATA_AUTH_MODE=none|basic|bearer
SAP_ODATA_USERNAME=...
SAP_ODATA_PASSWORD=...
SAP_ODATA_BEARER_TOKEN=...
```

Live mode validates required configuration before making requests. Missing configuration returns a sanitized error. Local verification does not make live SAP calls.

## Field Mapping

The connector maps common SAP/OData-style fields into canonical source material fields:

| OData Field | Canonical Field |
| --- | --- |
| `Material`, `MaterialCode`, `MATNR` | `source_material_code` |
| `MaterialDescription`, `Description`, `MAKTX` | `raw_description` |
| `BaseUnit`, `UOM`, `UnitOfMeasure` | `uom` |
| `MaterialGroup`, `Category` | `category` |
| `CompanyCode`, `CPSE` | `source_cpse` |
| `SourceSystem` | `source_system` |
| `ManufacturerName` | `manufacturer` |
| `ManufacturerPartNumber` | `part_number` |
| `ModelNumber` | `model_number` |
| `Plant`, `Specification` | non-sensitive metadata |

Normalization, attribute extraction, duplicate source-code rejection, row-error persistence, and audit events use the durable ingestion pipeline.

## Idempotency

`POST /api/integrations/sap/import-materials` accepts an optional `idempotency_key`.

Repeating an import with the same connector type and idempotency key returns the original `IntegrationImportRun` with `idempotent_replay=true` and does not create new materials or audit events.

## Security Rules

- Credentials are never returned by API responses.
- Credentials are not stored in import-run metadata, ingestion-batch metadata, source-material metadata, or audit events.
- Live errors are sanitized and do not include raw authorization headers, passwords, bearer tokens, or full exception payloads.
- Mock mode never performs external network access.

## Current Limitations

- Local verification does not validate a certified SAP authentication handshake.
- No scheduled sync or change-data-capture support yet.
- No SAP IDoc/BAPI support yet.
- No production credential vault integration yet.
- No SSO/RBAC enforcement yet.
- No connector UI is included in this prompt.
