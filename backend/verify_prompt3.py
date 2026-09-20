"""
Prompt 3 verification: durable CSV ingestion.

Uses a temporary SQLite database only. No developer or production database is touched.
"""

import asyncio
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlencode

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


def multipart_body(fields: dict, file_field: str, filename: str, content: bytes, content_type: str = "text/csv"):
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
        f"Content-Type: {content_type}\r\n\r\n".encode()
    )
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    return body, f"multipart/form-data; boundary={boundary}"


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


def upload_body(csv_text: str, filename: str = "materials.csv"):
    return multipart_body(
        {"source_cpse": "VERIFY_CPSE", "source_system": "VERIFY_ERP"},
        "file",
        filename,
        csv_text.encode("utf-8"),
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt3_") as tmp:
        db_path = Path(tmp) / "verify_prompt3.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import func, select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import IngestionBatch, IngestionRowError, SourceMaterial
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        csv_1 = """item_code,description,uom,category,manufacturer
MAT-001,BEARING 6205 ZZ,NOS,BEARINGS,SKF
MAT-002,BALL VALVE 50MM SS304 PN16,NOS,VALVES,L&T
"""

        preview_body, preview_type = upload_body(csv_1)
        st, preview = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/preview-csv",
            preview_body,
            [(b"content-type", preview_type.encode())],
        ))
        assert st == 200, f"preview-csv failed: {st}, {preview}"
        assert preview["summary"]["valid_records_count"] == 2
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(IngestionBatch)) == 0
            assert db.scalar(select(func.count()).select_from(SourceMaterial)) == 0

        ingest_body, ingest_type = upload_body(csv_1)
        st, ingest = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/ingest-csv",
            ingest_body,
            [(b"content-type", ingest_type.encode())],
        ))
        assert st == 200, f"ingest-csv failed: {st}, {ingest}"
        assert ingest["idempotent_replay"] is False
        assert ingest["processed_records"] == 2
        assert ingest["failed_records"] == 0
        batch_id = ingest["batch"]["id"]

        with SessionLocal() as db:
            batch = db.get(IngestionBatch, batch_id)
            assert batch is not None
            assert batch.status == "COMPLETED"
            assert batch.total_records == 2
            assert batch.processed_records == 2
            material = db.execute(
                select(SourceMaterial).where(SourceMaterial.source_material_code == "MAT-001")
            ).scalar_one()
            assert material.ingestion_batch_id == batch.id
            assert material.ingestion_batch.batch_name == batch.batch_name
            assert material.attributes.get("bearing_number") == "6205"
            assert material.metadata_json.get("row_number") == 2
            original_desc = material.raw_description

        st, batch_detail = asyncio.run(make_request(app, "GET", f"/api/materials/batches/{batch_id}"))
        assert st == 200, f"batch detail failed: {st}, {batch_detail}"
        assert batch_detail["batch"]["id"] == batch_id
        assert batch_detail["error_count"] == 0

        query = urlencode({"batch_id": batch_id, "page": 1, "limit": 10})
        st, materials = asyncio.run(make_request(app, "GET", f"/api/materials?{query}"))
        assert st == 200, f"materials by batch failed: {st}, {materials}"
        assert materials["total"] == 2
        assert materials["items"][0]["metadata_json"]["row_number"] in (2, 3)

        replay_body, replay_type = upload_body(csv_1)
        st, replay = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/ingest-csv",
            replay_body,
            [(b"content-type", replay_type.encode())],
        ))
        assert st == 200, f"idempotent replay failed: {st}, {replay}"
        assert replay["idempotent_replay"] is True
        assert replay["batch"]["id"] == batch_id
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(SourceMaterial)) == 2
            assert db.scalar(select(func.count()).select_from(IngestionBatch)) == 1

        csv_2 = """item_code,description,uom,category,manufacturer
MAT-001,CHANGED DESCRIPTION SHOULD NOT OVERWRITE,NOS,BEARINGS,OTHER
MAT-003,HEX BOLT M12X50 GRADE 8.8,NOS,FASTENERS,ACME
"""
        changed_body, changed_type = upload_body(csv_2, "materials_changed.csv")
        st, changed = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/ingest-csv",
            changed_body,
            [(b"content-type", changed_type.encode())],
        ))
        assert st == 200, f"changed ingest failed: {st}, {changed}"
        assert changed["idempotent_replay"] is False
        assert changed["processed_records"] == 1
        assert changed["failed_records"] == 1
        changed_batch_id = changed["batch"]["id"]

        with SessionLocal() as db:
            original = db.execute(
                select(SourceMaterial).where(SourceMaterial.source_material_code == "MAT-001")
            ).scalar_one()
            assert original.raw_description == original_desc
            new_material = db.execute(
                select(SourceMaterial).where(SourceMaterial.source_material_code == "MAT-003")
            ).scalar_one()
            assert new_material.ingestion_batch_id is not None
            error = db.execute(
                select(IngestionRowError).where(IngestionRowError.ingestion_batch_id == changed_batch_id)
            ).scalar_one()
            assert error.source_material_code == "MAT-001"
            assert "already exists" in error.reason

        with SessionLocal() as fresh_db:
            assert fresh_db.scalar(select(func.count()).select_from(SourceMaterial)) == 3
            assert fresh_db.scalar(select(func.count()).select_from(IngestionRowError)) == 1

        engine.dispose()

    print("PASS Prompt 3 durable CSV ingestion verified: preview non-persistence, ingest, retrieval, idempotency, duplicate row errors, fresh-session durability.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 3 verification failed: {exc}", file=sys.stderr)
        raise
