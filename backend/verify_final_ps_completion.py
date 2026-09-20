"""
Final Problem Statement completion verification.

Uses temporary SQLite databases only. Live SAP and trained ML are verified
honestly: missing credentials or optional ML dependencies are reported as
NOT_READY/SKIPPED rather than treated as fake production success.
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def auth(username: str, password: str) -> list[tuple[bytes, bytes]]:
    token = base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")
    return [(b"authorization", f"Basic {token}".encode("ascii"))]


async def make_request(app, method: str, path: str, body: bytes = b"", headers: list[tuple[bytes, bytes]] | None = None):
    if "?" in path:
        route_path, query_string = path.split("?", 1)
    else:
        route_path, query_string = path, ""
    all_headers = [(b"host", b"testserver")]
    if body:
        all_headers.append((b"content-length", str(len(body)).encode()))
    if headers:
        all_headers.extend(headers)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": route_path,
        "raw_path": route_path.encode("utf-8"),
        "query_string": query_string.encode("utf-8"),
        "headers": all_headers,
    }
    response_body = []
    status_code = 0
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    raw = b"".join(response_body).decode("utf-8")
    if not raw:
        return status_code, None
    try:
        return status_code, json.loads(raw)
    except json.JSONDecodeError:
        return status_code, raw


def post_json(app, path: str, payload: dict[str, Any], headers: list[tuple[bytes, bytes]]):
    return asyncio.run(make_request(app, "POST", path, json.dumps(payload).encode("utf-8"), [(b"content-type", b"application/json"), *headers]))


def multipart_body(fields: dict[str, Any], file_field: str, filename: str, content: bytes, content_type: str = "text/csv"):
    import uuid

    boundary = f"----namm-final-ps-{uuid.uuid4().hex}"
    chunks = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload(app, path: str, fields: dict[str, Any], filename: str, content: bytes, headers, content_type: str = "text/csv"):
    body, boundary = multipart_body(fields, "file", filename, content, content_type)
    return asyncio.run(make_request(app, "POST", path, body, [(b"content-type", boundary.encode()), *headers]))


def make_xlsx(rows: list[dict[str, Any]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header) for header in headers])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def extract_json(stdout: str) -> dict:
    start = stdout.find("{")
    if start < 0:
        raise AssertionError(f"No JSON summary found:\n{stdout}")
    return json.loads(stdout[start:])


def run_existing_verify_scripts(env: dict[str, str]) -> None:
    for script in sorted(BACKEND_DIR.glob("verify*.py"), key=lambda p: p.name):
        if script.name == Path(__file__).name:
            continue
        print(f"Checking existing verifier: {script.name}", flush=True)
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=240,
        )
        if result.returncode != 0:
            raise AssertionError(f"{script.name} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="namm_final_ps_demo_"))
    engine = None
    try:
        db_path = tmp / "final_ps.db"
        db_url = f"sqlite:///{db_path.as_posix()}"
        env = os.environ.copy()
        env.update({
            "DATABASE_URL": db_url,
            "SAP_ODATA_MODE": "mock",
            "SAP_ODATA_ENTITY_SET": "A_Material",
            "EMBEDDING_PROVIDER": "stub",
            "EMBEDDING_ALLOW_STUB_FALLBACK": "true",
            "PYTHONPATH": str(BACKEND_DIR),
        })

        print("Running production demo bootstrap...", flush=True)
        demo = subprocess.run(
            [sys.executable, str(BACKEND_DIR / "run_production_demo.py"), "--database-url", db_url, "--fresh"],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert demo.returncode == 0, demo.stderr
        demo_summary = extract_json(demo.stdout)
        assert demo_summary["national_material_status"] == "ACTIVE"
        national_code = demo_summary["national_material_code"]

        print("Importing app against final PS database...", flush=True)
        os.environ.update(env)
        from app.core.config import settings
        from app.db.session import engine as db_engine
        from main import app

        engine = db_engine
        admin_h = auth("demo_admin", "demo-admin-pass")
        cpse_h = auth("demo_cpse", "demo-cpse-pass")
        l2_h = auth("demo_l2", "demo-l2-pass")
        auditor_h = auth("demo_auditor", "demo-auditor-pass")

        print("Verifying taxonomy governance...", flush=True)
        # 1. Taxonomy creation/versioning and validation.
        st, taxonomy = asyncio.run(make_request(app, "GET", "/api/taxonomy/nodes"))
        assert st == 200 and taxonomy["count"] >= 6
        st, created = post_json(app, "/api/taxonomy/nodes", {
            "category": "filters",
            "sub_category": "oil",
            "material_type": "filter",
            "display_name": "Oil Filters",
            "allowed_units": ["EA"],
            "attributes": [{"attribute_key": "micron_rating", "mandatory": True, "matching_critical": True}],
        }, admin_h)
        assert st == 200
        node_id = created["item"]["id"]
        st, updated = asyncio.run(make_request(app, "PATCH", f"/api/taxonomy/nodes/{node_id}", json.dumps({"display_name": "Oil Filters v2"}).encode(), [(b"content-type", b"application/json"), *admin_h]))
        assert st == 200 and updated["item"]["version"] >= 2
        st, validation = post_json(app, "/api/taxonomy/validate", {"category": "filters", "uom": "EA", "attributes": {}}, admin_h)
        assert st == 200 and validation["validation"]["errors"]
        st, deprecated = asyncio.run(make_request(app, "POST", f"/api/taxonomy/nodes/{node_id}/deprecate", headers=admin_h))
        assert st == 200 and deprecated["lifecycle_status"] == "DEPRECATED"

        print("Verifying legacy migration workbench...", flush=True)
        # 2. CSV/XLSX legacy migration dry-run, import, error report, rollback.
        legacy_csv = b"item_code,description,uom,category\nLEG-1,DEEP GROOVE BALL BEARING 6205 2RS,NOS,BEARINGS\nBAD-1,,EA,BEARINGS\n"
        print(" - migration dry-run", flush=True)
        st, dry = upload(app, "/api/migration/legacy-materials", {"source_cpse": "LEGACY_CPSE", "source_system": "LEGACY_ERP", "dry_run": "true"}, "legacy.csv", legacy_csv, admin_h)
        assert st == 200 and dry["job"]["dry_run"] is True and dry["job"]["rejected_records"] >= 1
        print(" - migration xlsx import", flush=True)
        xlsx = make_xlsx([{"item_code": "ROLL-1", "description": "HEX BOLT M12 X 50 GRADE 8.8", "uom": "EA", "category": "FASTENERS"}])
        st, imported = upload(app, "/api/migration/legacy-materials", {"source_cpse": "ROLLBACK_CPSE", "source_system": "XLSX_ERP", "dry_run": "false"}, "legacy.xlsx", xlsx, admin_h, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert st == 200 and imported["job"]["ingestion_batch_id"]
        print(" - migration error csv", flush=True)
        st, errors_csv = asyncio.run(make_request(app, "GET", f"/api/migration/jobs/{dry['job']['id']}/errors.csv", headers=admin_h))
        assert st == 200 and "row_number" in errors_csv if isinstance(errors_csv, str) else st == 200
        print(" - migration rollback", flush=True)
        st, rolled = asyncio.run(make_request(app, "POST", f"/api/migration/jobs/{imported['job']['id']}/rollback", headers=admin_h))
        assert st == 200 and rolled["job"]["rollback_status"] == "ROLLED_BACK"

        print("Verifying procurement history...", flush=True)
        # 3. Procurement-history import and actual-spend analytics.
        procurement_csv = b"cpse,source_system,source_material_code,date,quantity,uom,unit_price,total_amount,vendor,po_reference\nDEMO_CPSE,CSV_DEMO_ERP,DEMO-CSV-BRG-6205,2026-09-20,10,EA,500,5000,Vendor A,PO-1\n"
        st, proc_import = upload(app, "/api/procurement/history/import", {}, "procurement.csv", procurement_csv, cpse_h)
        assert st == 200 and proc_import["imported_count"] == 1
        st, proc_analytics = asyncio.run(make_request(app, "GET", "/api/procurement/analytics", headers=auditor_h))
        assert st == 200 and proc_analytics["actual_total_spend"] == 5000
        st, analytics = asyncio.run(make_request(app, "GET", "/api/analytics/summary?days=30"))
        assert st == 200 and analytics["actual_procurement_spend_inr"] >= 5000

        print("Verifying ML readiness...", flush=True)
        # 4-5. ML refusal and optional training/inference readiness.
        st, refused = post_json(app, "/api/ml/train", {"min_labels": 999}, admin_h)
        assert st == 422 and "Insufficient labelled decisions" in str(refused)
        st, labels = asyncio.run(make_request(app, "GET", "/api/ml/labels/export", headers=auditor_h))
        assert st == 200 and labels["count"] >= 2
        st, model = post_json(app, "/api/ml/train", {"min_labels": 1}, admin_h)
        assert st == 200 and model["status"] in {"SKIPPED_DEPENDENCIES_MISSING", "SKIPPED_NOT_ENABLED", "TRAINED"}
        st, model_eval = asyncio.run(make_request(app, "GET", "/api/ml/evaluate", headers=auditor_h))
        assert st == 200 and model_eval["rule_baseline"]["status"] == "ACTIVE"

        print("Verifying SAP readiness...", flush=True)
        # 6. SAP mock preflight/import and safe live missing-config failure.
        st, preflight = asyncio.run(make_request(app, "GET", "/api/integrations/sap/preflight", headers=auditor_h))
        assert st == 200 and preflight["status"] == "READY"
        st, sap_import = post_json(app, "/api/integrations/sap/import-materials", {
            "source_cpse": "PS_SAP_CPSE",
            "source_system": "SAP_PS_VERIFY",
            "connection_name": "ps-final-mock",
            "idempotency_key": "ps-final-mock",
            "max_records": 1,
        }, cpse_h)
        assert st == 200 and sap_import["connector_metadata"]["mode"] == "mock"
        settings.SAP_ODATA_MODE = "live"
        settings.SAP_ODATA_BASE_URL = ""
        settings.SAP_ODATA_AUTH_MODE = "basic"
        settings.SAP_ODATA_USERNAME = ""
        settings.SAP_ODATA_PASSWORD = ""
        st, live_preflight = asyncio.run(make_request(app, "GET", "/api/integrations/sap/preflight", headers=auditor_h))
        assert st == 200 and live_preflight["status"] == "NOT_READY" and "SAP_ODATA_BASE_URL" in live_preflight["missing"]
        settings.SAP_ODATA_MODE = "mock"
        st, sync_cfg = post_json(app, "/api/integrations/sap/sync-configurations", {
            "connection_name": "ps-final-config",
            "source_cpse": "PS_SAP_CPSE",
            "source_system": "SAP_PS_VERIFY",
            "entity_set": "A_Material",
            "mode": "mock",
        }, admin_h)
        assert st == 200 and sync_cfg["configuration"]["secrets_persisted"] is False

        print("Verifying national-code lifecycle governance...", flush=True)
        # 7. National-code revision/deprecation/replacement governance.
        st, change = post_json(app, f"/api/national-governance/materials/{national_code}/change-request", {"change_type": "DESCRIPTION_REVIEW", "reason": "PS final verification"}, admin_h)
        assert st == 200 and change["material_status"] == "UNDER_REVIEW"
        st, deprecated = post_json(app, f"/api/national-governance/materials/{national_code}/deprecate", {}, l2_h)
        assert st == 200 and deprecated["material_status"] == "DEPRECATED"
        st, revisions = asyncio.run(make_request(app, "GET", f"/api/national-governance/materials/{national_code}/revisions"))
        assert st == 200 and revisions["count"] >= 2

        print("Verifying frontend API contracts...", flush=True)
        # 8. Authenticated production frontend API contracts.
        st, me = asyncio.run(make_request(app, "GET", "/api/auth/me", headers=admin_h))
        assert st == 200 and me["roles"]
        st, cases = asyncio.run(make_request(app, "GET", "/api/approvals/cases", headers=auditor_h))
        assert st == 200 and "items" in cases
        st, audit_events = asyncio.run(make_request(app, "GET", "/api/audit/events?limit=25", headers=auditor_h))
        assert st == 200 and audit_events["total"] > 0

        print("Verifying audit and demo compatibility...", flush=True)
        # 9-10. End-to-end already established; audit must remain intact after all actions.
        st, audit_verify = asyncio.run(make_request(app, "POST", "/api/audit/verify", headers=auditor_h))
        assert st == 200 and audit_verify["status"] == "CHAIN_INTACT"

        # 11. Existing demo endpoints still function.
        st, demo_queue = asyncio.run(make_request(app, "GET", "/api/approvals/demo-queue"))
        assert st == 200 and demo_queue["total_cases"] >= 1
        st, demo_audit = asyncio.run(make_request(app, "GET", "/api/audit/demo-verify"))
        assert st == 200 and demo_audit["chain_status"] == "CHAIN_INTACT"

        if engine is not None:
            engine.dispose()
            engine = None

        # 12. Existing verify scripts pass. Exclude this file to avoid recursion.
        print("Running existing verify script sweep...", flush=True)
        run_existing_verify_scripts(env)

    finally:
        if engine is not None:
            engine.dispose()
        shutil.rmtree(tmp, ignore_errors=True)

    print(
        "PASS Final PS completion verified: taxonomy, migration, procurement history, ML honesty, SAP readiness, "
        "national governance, production API contracts, end-to-end workflow, audit integrity, demo compatibility, and prior verify scripts."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Final PS completion verification failed: {exc}", file=sys.stderr)
        raise
