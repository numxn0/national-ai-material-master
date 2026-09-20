"""
Prompt 10 verification: durable SAP OData integration interface with mock connector.

Uses a temporary SQLite database only. No real SAP credentials are used and no live
external request is made during verification.
"""

import asyncio
import json
import os
import sys
import shutil
import tempfile
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

DEFAULT_HEADERS: list[tuple[bytes, bytes]] = []


def install_verify_admin(SessionLocal):
    from app.services.auth import create_or_update_local_user

    with SessionLocal() as db:
        create_or_update_local_user(
            db,
            username="verify_admin",
            password="verify-pass",
            display_name="Verify Admin",
            roles=["ADMIN", "AUDITOR"],
        )
    global DEFAULT_HEADERS
    DEFAULT_HEADERS = [(b"authorization", b"Basic dmVyaWZ5X2FkbWluOnZlcmlmeS1wYXNz")]


async def make_request(app, method: str, path: str, body: bytes = b"", headers: list[tuple[bytes, bytes]] | None = None):
    if "?" in path:
        route_path, query_string = path.split("?", 1)
    else:
        route_path, query_string = path, ""
    all_headers = [(b"host", b"testserver"), *DEFAULT_HEADERS]
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


def json_body(payload: dict):
    return json.dumps(payload).encode("utf-8"), "application/json"


def post_json(app, path: str, payload: dict):
    body, content_type = json_body(payload)
    return asyncio.run(make_request(app, "POST", path, body, [(b"content-type", content_type.encode())]))


def multipart_body(fields: dict, file_field: str, filename: str, content: bytes):
    boundary = f"----namm-{uuid.uuid4().hex}"
    chunks = []
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
    body = b"".join(chunks)
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="namm_prompt10_sap_")
    engine = None
    try:
        db_path = Path(tmp) / "verify_prompt10.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ["SAP_ODATA_MODE"] = "mock"
        os.environ["SAP_ODATA_ENTITY_SET"] = "A_Material"
        os.environ["EMBEDDING_PROVIDER"] = "stub"
        os.environ["EMBEDDING_DIMENSIONS"] = "64"
        os.environ["EMBEDDING_ALLOW_STUB_FALLBACK"] = "true"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import func, select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.core.config import settings
        from app.db.models import AuditEvent, IngestionBatch, IntegrationImportRun, SourceMaterial
        from app.db.session import SessionLocal, engine as db_engine
        from main import app
        engine = db_engine
        install_verify_admin(SessionLocal)

        settings.SAP_ODATA_MODE = "mock"
        settings.SAP_ODATA_ENTITY_SET = "A_Material"
        settings.EMBEDDING_PROVIDER = "stub"
        settings.EMBEDDING_DIMENSIONS = 64
        settings.EMBEDDING_ALLOW_STUB_FALLBACK = True

        st, connection = asyncio.run(make_request(app, "POST", "/api/integrations/sap/test-connection"))
        assert st == 200, f"mock test connection failed: {st}, {connection}"
        assert connection["connector_mode"] == "mock"
        assert connection["metadata"]["external_network"] is False
        assert connection["capabilities"]["network_required"] is False
        assert "PASSWORD" not in json.dumps(connection).upper()

        import_payload = {
            "source_cpse": "SAP_MOCK_CPSE",
            "source_system": "SAP_ODATA_VERIFY",
            "connection_name": "prompt10-mock-sap",
            "entity_set": "A_Material",
            "max_records": 3,
            "idempotency_key": "prompt10-sap-import-key",
        }
        st, imported = post_json(app, "/api/integrations/sap/import-materials", import_payload)
        assert st == 200, f"mock import failed: {st}, {imported}"
        assert imported["idempotent_replay"] is False
        assert imported["received_count"] == 3
        assert imported["imported_count"] == 3
        assert imported["rejected_count"] == 0
        assert imported["connector_metadata"]["mode"] == "mock"
        run_id = imported["import_run"]["id"]
        batch_id = imported["ingestion_batch"]["id"]

        with SessionLocal() as db:
            run = db.get(IntegrationImportRun, uuid.UUID(run_id))
            assert run is not None and str(run.ingestion_batch_id) == batch_id
            assert run.status == "COMPLETED"
            assert run.metadata_json["connector"]["mode"] == "mock"
            batch = db.get(IngestionBatch, uuid.UUID(batch_id))
            assert batch is not None and batch.processed_records == 3
            assert batch.metadata_json["connector_type"] == "sap_odata"
            assert batch.metadata_json["received_record_count"] == 3
            assert db.scalar(select(func.count()).select_from(SourceMaterial).where(SourceMaterial.ingestion_batch_id == uuid.UUID(batch_id))) == 3
            actions = set(db.execute(select(AuditEvent.action)).scalars().all())
            assert "ERP_IMPORT_STARTED" in actions
            assert "ERP_IMPORT_COMPLETED" in actions
            serialized = json.dumps(run.metadata_json)
            assert "SecretShouldNotLeak" not in serialized

        st, detail = asyncio.run(make_request(app, "GET", f"/api/integrations/import-runs/{run_id}"))
        assert st == 200, f"import run detail failed: {st}, {detail}"
        assert detail["import_run"]["id"] == run_id
        assert detail["ingestion_batch"]["id"] == batch_id

        st, replay = post_json(app, "/api/integrations/sap/import-materials", import_payload)
        assert st == 200, f"idempotent replay failed: {st}, {replay}"
        assert replay["idempotent_replay"] is True
        assert replay["import_run"]["id"] == run_id
        assert replay["received_count"] == imported["received_count"]
        assert replay["imported_count"] == imported["imported_count"]
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(IntegrationImportRun)) == 1
            assert db.scalar(select(func.count()).select_from(SourceMaterial).where(SourceMaterial.ingestion_batch_id == uuid.UUID(batch_id))) == 3

        st, matching = post_json(app, f"/api/matching/run/{batch_id}", {"min_score": 0.55})
        assert st == 200, f"matching imported batch failed: {st}, {matching}"
        assert matching["candidate_count"] >= 1
        st, match_results = asyncio.run(make_request(app, "GET", f"/api/matching/results/{batch_id}"))
        assert st == 200 and match_results["items"], f"matching results missing: {st}, {match_results}"

        csv_text = """item_code,description,uom,category,manufacturer
CSV-SAP-VERIFY-1,HEX BOLT M12 X 50 GRADE 8.8 ZINC,NOS,FASTENERS,LOCAL
"""
        body, content_type = multipart_body(
            {"source_cpse": "CSV_VERIFY_CPSE", "source_system": "CSV_VERIFY"},
            "file",
            "csv_verify.csv",
            csv_text.encode("utf-8"),
        )
        st, csv_ingest = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body, [(b"content-type", content_type.encode())]))
        assert st == 200 and csv_ingest["processed_records"] == 1, f"CSV ingestion regression failed: {st}, {csv_ingest}"
        st, demo = asyncio.run(make_request(app, "GET", "/api/demo/summary"))
        assert st == 200 and demo["sample_material_count"] == 10, f"demo regression failed: {st}, {demo}"

        settings.SAP_ODATA_MODE = "live"
        settings.SAP_ODATA_BASE_URL = ""
        settings.SAP_ODATA_AUTH_MODE = "basic"
        settings.SAP_ODATA_USERNAME = "prompt10-user"
        settings.SAP_ODATA_PASSWORD = "SecretShouldNotLeak"
        st, live_missing = asyncio.run(make_request(app, "POST", "/api/integrations/sap/test-connection"))
        assert st == 400, f"live missing config should fail with 400: {st}, {live_missing}"
        live_text = json.dumps(live_missing)
        assert "SecretShouldNotLeak" not in live_text
        assert "SAP_ODATA_PASSWORD" not in live_text
        assert "SAP_ODATA_BASE_URL" in live_text

    finally:
        if engine is not None:
            engine.dispose()
        shutil.rmtree(tmp, ignore_errors=True)

    print(
        "PASS Prompt 10 SAP OData integration verified: mock connection, durable import run, "
        "ingestion reuse, audit events, idempotency, imported matching, live missing-config sanitization, CSV/demo regressions."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 10 SAP OData verification failed: {exc}", file=sys.stderr)
        raise
