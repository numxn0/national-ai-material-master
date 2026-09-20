"""
Reproducible durable production workflow demonstration.

The demo intentionally runs through the FastAPI API surface so authentication,
router dependencies, database sessions, migrations, SAP mock import, matching,
approvals, audit verification, and analytics are exercised together.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class DemoError(Exception):
    pass


def auth_header(username: str, password: str) -> list[tuple[bytes, bytes]]:
    token = base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")
    return [(b"authorization", f"Basic {token}".encode("ascii"))]


async def make_request(
    app,
    method: str,
    path: str,
    body: bytes = b"",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> tuple[int, Any]:
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
    response_body: list[bytes] = []
    status_code = 0
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    raw = b"".join(response_body).decode("utf-8")
    return status_code, json.loads(raw) if raw else None


def post_json(app, path: str, payload: dict[str, Any], headers: list[tuple[bytes, bytes]]):
    body = json.dumps(payload).encode("utf-8")
    return asyncio.run(make_request(app, "POST", path, body, [(b"content-type", b"application/json"), *headers]))


def multipart_body(fields: dict[str, str], file_field: str, filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = f"----namm-demo-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}\r\n".encode())
    chunks.append(
        f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n".encode()
    )
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def require_status(status: int, payload: Any, expected: int, label: str) -> Any:
    if status != expected:
        raise DemoError(f"{label} failed with HTTP {status}: {payload}")
    return payload


def safe_database_url(database_url: str) -> str:
    return make_url(database_url).render_as_string(hide_password=True)


def sqlite_file_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return None
    if url.database in (None, "", ":memory:"):
        raise DemoError("--fresh requires a SQLite file database, not an in-memory SQLite URL.")
    path = Path(url.database).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_fresh_sqlite_target(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        raise DemoError("--fresh is only supported for SQLite file databases. PostgreSQL/Supabase URLs are never reset.")

    db_path = sqlite_file_path(database_url)
    if db_path is None:
        raise DemoError("--fresh requires a SQLite file database.")
    if db_path.exists() and db_path.is_dir():
        raise DemoError(f"--fresh target is a directory, not a SQLite file: {db_path}")
    if db_path.parent == db_path or not db_path.name:
        raise DemoError(f"--fresh target is not a safe SQLite file path: {db_path}")

    backend_data = (BACKEND_DIR / "data").resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    parent_names = {parent.name.lower() for parent in db_path.parents if parent.resolve() != system_temp}
    in_backend_data = _is_relative_to(db_path, backend_data)
    in_named_demo_dir = any("demo" in name or "temp" in name or "tmp" in name for name in parent_names)
    if not (in_backend_data or in_named_demo_dir):
        raise DemoError(
            "--fresh refused: SQLite file must be under backend/data or inside an explicitly named demo/temp directory."
        )
    return db_path


def recreate_sqlite_file(db_path: Path) -> None:
    print(f"Recreating SQLite demo database file: {db_path}", flush=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    for path in [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]:
        if path.exists():
            if path.is_dir():
                raise DemoError(f"Refusing to delete directory: {path}")
            path.unlink()


def configure_environment(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("SAP_ODATA_MODE", "mock")
    os.environ.setdefault("SAP_ODATA_ENTITY_SET", "A_Material")
    os.environ.setdefault("EMBEDDING_PROVIDER", "stub")
    os.environ.setdefault("EMBEDDING_ALLOW_STUB_FALLBACK", "true")
    os.environ.setdefault("EMBEDDING_DIMENSIONS", "64")


def apply_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


def create_demo_users(SessionLocal) -> dict[str, list[tuple[bytes, bytes]]]:
    from app.services.auth import create_or_update_local_user

    users = {
        "admin": ("demo_admin", "demo-admin-pass", "Demo Admin", ["ADMIN"]),
        "cpse": ("demo_cpse", "demo-cpse-pass", "Demo CPSE User", ["CPSE_USER"]),
        "l1": ("demo_l1", "demo-l1-pass", "Demo L1 Reviewer", ["L1_REVIEWER"]),
        "l2": ("demo_l2", "demo-l2-pass", "Demo L2 Authority", ["L2_AUTHORITY"]),
        "auditor": ("demo_auditor", "demo-auditor-pass", "Demo Auditor", ["AUDITOR"]),
    }
    with SessionLocal() as db:
        for username, password, display_name, roles in users.values():
            create_or_update_local_user(
                db,
                username=username,
                password=password,
                display_name=display_name,
                roles=roles,
                organization_scope=None,
            )
    return {key: auth_header(username, password) for key, (username, password, _, _) in users.items()}


def upload_demo_csv(app, headers: list[tuple[bytes, bytes]]) -> dict[str, Any]:
    csv_text = """item_code,description,uom,category,manufacturer,part_number
DEMO-CSV-BRG-6205,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF,6205-2RS-C3
"""
    body, content_type = multipart_body(
        {"source_cpse": "DEMO_CPSE", "source_system": "CSV_DEMO_ERP"},
        "file",
        "production_demo_materials.csv",
        csv_text.encode("utf-8"),
    )
    status, payload = asyncio.run(
        make_request(app, "POST", "/api/materials/ingest-csv", body, [(b"content-type", content_type.encode()), *headers])
    )
    return require_status(status, payload, 200, "CSV ingestion")


def select_candidate(results: dict[str, Any]) -> dict[str, Any]:
    items = results.get("items") or []
    if not items:
        raise DemoError("Matching produced no persisted candidates.")

    def candidate_key(item: dict[str, Any]) -> tuple[int, float]:
        codes = {
            (item.get("source_material_a") or {}).get("source_material_code"),
            (item.get("source_material_b") or {}).get("source_material_code"),
        }
        has_csv = any(str(code or "").startswith("DEMO-CSV") for code in codes)
        has_sap = any(str(code or "").startswith("SAP-") for code in codes)
        score = item.get("hybrid_score") if item.get("hybrid_score") is not None else item.get("candidate_score", 0.0)
        return (1 if has_csv and has_sap else 0, float(score or 0.0))

    return max(items, key=candidate_key)


def run_demo(database_url: str, *, fresh: bool = False) -> dict[str, Any]:
    if fresh:
        recreate_sqlite_file(validate_fresh_sqlite_target(database_url))

    configure_environment(database_url)
    apply_migrations()

    from app.core.config import settings
    from app.db.session import SessionLocal, engine
    from main import app

    settings.SAP_ODATA_MODE = os.environ.get("SAP_ODATA_MODE", "mock")
    settings.SAP_ODATA_ENTITY_SET = os.environ.get("SAP_ODATA_ENTITY_SET", "A_Material")
    settings.EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "stub")
    settings.EMBEDDING_ALLOW_STUB_FALLBACK = os.environ.get("EMBEDDING_ALLOW_STUB_FALLBACK", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    try:
        headers = create_demo_users(SessionLocal)

        csv_ingest = upload_demo_csv(app, headers["cpse"])
        csv_batch_id = csv_ingest["batch"]["id"]

        sap_payload = {
            "source_cpse": "SAP_MOCK_CPSE",
            "source_system": "SAP_ODATA_DEMO",
            "connection_name": "production-demo-mock-sap",
            "entity_set": "A_Material",
            "max_records": 2,
            "idempotency_key": "production-demo-sap-import-v1",
        }
        sap_import = require_status(
            *post_json(app, "/api/integrations/sap/import-materials", sap_payload, headers["cpse"]),
            expected=200,
            label="SAP mock import",
        )
        sap_batch_id = sap_import["ingestion_batch"]["id"]
        sap_import_run_id = sap_import["import_run"]["id"]

        matching = require_status(
            *post_json(app, f"/api/matching/run/{sap_batch_id}", {"min_score": 0.45}, headers["cpse"]),
            expected=200,
            label="Persistent matching",
        )
        if matching["candidate_count"] < 1:
            raise DemoError("Persistent matching completed without candidates.")

        status, match_results = asyncio.run(make_request(app, "GET", f"/api/matching/results/{sap_batch_id}?limit=20"))
        match_results = require_status(status, match_results, 200, "Fetch matching results")
        candidate = select_candidate(match_results)
        candidate_id = candidate["id"]

        status, draft = asyncio.run(
            make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}", headers=headers["cpse"])
        )
        draft = require_status(status, draft, 200, "Create national material draft")
        national_code = draft["national_material"]["national_material_code"]

        status, approval_case = asyncio.run(
            make_request(app, "POST", f"/api/approvals/cases/from-national-material/{national_code}", headers=headers["cpse"])
        )
        approval_case = require_status(status, approval_case, 200, "Create approval case")
        approval_case_id = approval_case["case"]["id"]

        l1 = require_status(
            *post_json(
                app,
                f"/api/approvals/cases/{approval_case_id}/decision",
                {"decision": "APPROVE", "reviewer_note": "L1 production demo approval."},
                headers["l1"],
            ),
            expected=200,
            label="L1 approval",
        )
        if l1["case"]["current_stage"] != "PENDING_L2":
            raise DemoError(f"L1 approval did not advance to PENDING_L2: {l1['case']['current_stage']}")

        l2 = require_status(
            *post_json(
                app,
                f"/api/approvals/cases/{approval_case_id}/decision",
                {"decision": "APPROVE", "reviewer_note": "L2 production demo approval."},
                headers["l2"],
            ),
            expected=200,
            label="L2 approval",
        )
        final_case = l2["case"]
        if final_case["approval_status"] != "APPROVED":
            raise DemoError(f"Approval case final status is not APPROVED: {final_case['approval_status']}")

        status, national = asyncio.run(make_request(app, "GET", f"/api/national-materials/{national_code}", headers=headers["admin"]))
        national = require_status(status, national, 200, "Fetch active national material")
        if national["national_material"]["status"] != "ACTIVE":
            raise DemoError(f"National material is not ACTIVE: {national['national_material']['status']}")
        approved_mappings = [m for m in national["mappings"] if m["approval_status"] == "APPROVED"]
        if len(approved_mappings) != 2:
            raise DemoError(f"Expected two approved mappings, found {len(approved_mappings)}.")

        status, analytics = asyncio.run(make_request(app, "GET", "/api/analytics/summary?days=30", headers=headers["admin"]))
        analytics = require_status(status, analytics, 200, "Fetch analytics summary")

        status, audit_verify = asyncio.run(make_request(app, "POST", "/api/audit/verify", headers=headers["auditor"]))
        audit_verify = require_status(status, audit_verify, 200, "Verify audit chain")
        if audit_verify["status"] != "CHAIN_INTACT":
            raise DemoError(f"Audit chain status is not CHAIN_INTACT: {audit_verify['status']}")

        return {
            "database_url": safe_database_url(database_url),
            "ingestion_batch_ids": {
                "csv": csv_batch_id,
                "sap": sap_batch_id,
            },
            "sap_import_run_id": sap_import_run_id,
            "match_candidate": {
                "id": candidate_id,
                "candidate_score": candidate["candidate_score"],
                "hybrid_score": candidate.get("hybrid_score"),
                "classification": candidate.get("classification"),
                "score_details": {
                    "has_persistent_semantic_embedding": "persistent_semantic_embedding" in (candidate.get("score_details") or {}),
                    "method_version": candidate.get("method_version"),
                },
            },
            "national_material_code": national_code,
            "national_material_status": national["national_material"]["status"],
            "mapped_cpse_source_codes": final_case["mapping_preview"].get("source_material_codes", []),
            "approved_mapping_count": len(approved_mappings),
            "approval_case": {
                "id": approval_case_id,
                "case_id": final_case["approval_case_id"],
                "current_stage": final_case["current_stage"],
                "approval_status": final_case["approval_status"],
            },
            "audit_chain": {
                "status": audit_verify["status"],
                "event_count": audit_verify["total_events"],
                "verified_events": audit_verify["verified_events"],
            },
            "analytics_headline_counts": {
                "total_source_materials": analytics["total_source_materials"],
                "total_ingestion_batches": analytics["total_ingestion_batches"],
                "total_match_candidates": analytics["total_match_candidates"],
                "national_material_active_count": analytics["national_material_active_count"],
                "approved_mapping_count": analytics["approved_mapping_count"],
                "audit_event_count": analytics["audit_event_count"],
            },
            "demo_modes": {
                "sap": f"{settings.SAP_ODATA_MODE} mode; mock mode is the safe default.",
                "embeddings": (
                    f"{settings.EMBEDDING_PROVIDER} provider; stub embeddings are used unless configured otherwise."
                ),
            },
        }
    finally:
        engine.dispose()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the durable National AI Material Master production demo flow.")
    parser.add_argument("--database-url", required=True, help="Explicit database URL for the demo run.")
    parser.add_argument("--fresh", action="store_true", help="Recreate a safe SQLite file database before running.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_demo(args.database_url, fresh=args.fresh)
    except Exception as exc:
        print(f"FAIL production demo: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
