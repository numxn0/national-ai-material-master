"""
Prompt 2 verification: durable database foundation.

Uses a temporary SQLite database only. No developer or production database is touched.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))


async def make_request(app, method: str, path: str):
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [(b"host", b"testserver")],
    }
    response_body = []
    status_code = 0

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_body.append(message.get("body", b""))

    await app(scope, receive, send)
    body = b"".join(response_body).decode("utf-8")
    return status_code, json.loads(body) if body else None


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt2_") as tmp:
        db_path = Path(tmp) / "verify_prompt2.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import IngestionBatch, SourceMaterial
        from app.db.session import SessionLocal, engine

        with SessionLocal() as db:
            batch = IngestionBatch(
                batch_name="VERIFY-PROMPT2-BATCH",
                source_cpse="VERIFY_CPSE",
                source_system="VERIFY_ERP",
                file_name="verify_materials.csv",
                uploaded_by="verify_prompt2",
                total_records=1,
                processed_records=1,
                failed_records=0,
                status="COMPLETED",
                error_summary={},
                metadata_json={"purpose": "prompt2 verification"},
            )
            material = SourceMaterial(
                ingestion_batch=batch,
                source_cpse="VERIFY_CPSE",
                source_system="VERIFY_ERP",
                source_material_code="VERIFY-MAT-001",
                raw_description="BEARING 6205 ZZ",
                cleaned_description="bearing 6205 zz",
                standard_description="BEARING 6205 ZZ",
                category="BEARINGS",
                sub_category="BALL_BEARINGS",
                uom="EA",
                attributes={"bearing_number": "6205", "seal_type": "ZZ"},
                normalized_tokens=["BEARING", "6205", "ZZ"],
                metadata_json={"row_number": 1},
            )
            db.add(material)
            db.commit()

            loaded = db.execute(
                select(SourceMaterial).where(SourceMaterial.source_material_code == "VERIFY-MAT-001")
            ).scalar_one()

            assert loaded.ingestion_batch is not None, "Source material should be related to its ingestion batch."
            assert loaded.ingestion_batch.batch_name == "VERIFY-PROMPT2-BATCH"
            assert loaded.attributes["bearing_number"] == "6205"

            duplicate = SourceMaterial(
                ingestion_batch_id=loaded.ingestion_batch_id,
                source_cpse="VERIFY_CPSE",
                source_system="VERIFY_ERP",
                source_material_code="VERIFY-MAT-001",
                raw_description="DUPLICATE BEARING 6205 ZZ",
                category="BEARINGS",
                sub_category="BALL_BEARINGS",
                uom="EA",
                attributes={},
                normalized_tokens=[],
                metadata_json={},
            )
            db.add(duplicate)
            try:
                db.commit()
                raise AssertionError("Duplicate source material origin/code should violate unique constraint.")
            except IntegrityError:
                db.rollback()

        from main import app

        status, body = asyncio.run(make_request(app, "GET", "/health/ready"))
        assert status == 200, f"/health/ready returned {status}: {body}"
        assert body["database"] == "reachable"

        assert db_path.exists(), "Temporary SQLite database file was not created."
        engine.dispose()

    print("PASS Prompt 2 database foundation verified: migration, ORM insert/read, relationship, uniqueness, readiness endpoint.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 2 verification failed: {exc}", file=sys.stderr)
        raise
