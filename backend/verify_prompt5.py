"""
Prompt 5 verification: durable national material draft registry.

Uses a temporary SQLite database only. No developer or production database is touched.
"""

import asyncio
import json
import os
import sys
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


def upload_body(csv_text: str, source_cpse: str, filename: str):
    return multipart_body(
        {"source_cpse": source_cpse, "source_system": "VERIFY_ERP"},
        "file",
        filename,
        csv_text.encode("utf-8"),
    )


def json_body(payload: dict):
    return json.dumps(payload).encode("utf-8"), "application/json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt5_") as tmp:
        db_path = Path(tmp) / "verify_prompt5.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import func, select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import MatchCandidate, MaterialMapping, NationalMaterial
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        csv_a = """item_code,description,uom,category,manufacturer
RAIL-BRG-6205,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF
"""
        csv_b = """item_code,description,uom,category,manufacturer
BHEL-BRG-6205,BALL BEARING 6205-2RS DEEP GROOVE SKF,NOS,BEARINGS,SKF
"""
        body_a, type_a = upload_body(csv_a, "RAILWAYS", "rail_registry.csv")
        st, _ = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_a, [(b"content-type", type_a.encode())]))
        assert st == 200

        body_b, type_b = upload_body(csv_b, "BHEL", "bhel_registry.csv")
        st, ingest_b = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_b, [(b"content-type", type_b.encode())]))
        assert st == 200
        batch_b = ingest_b["batch"]["id"]

        run_body, run_type = json_body({"min_score": 0.65})
        st, run = asyncio.run(make_request(app, "POST", f"/api/matching/run/{batch_b}", run_body, [(b"content-type", run_type.encode())]))
        assert st == 200 and run["candidate_count"] >= 1

        with SessionLocal() as db:
            candidate = db.execute(select(MatchCandidate).order_by(MatchCandidate.hybrid_score.desc())).scalars().first()
            assert candidate is not None
            candidate_id = str(candidate.id)
            source_ids = {str(candidate.source_material_a_id), str(candidate.source_material_b_id)}

        st, draft = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}"))
        assert st == 200, f"draft creation failed: {st}, {draft}"
        assert draft["idempotent_replay"] is False
        national = draft["national_material"]
        code = national["national_material_code"]
        assert code.startswith("NAMM-")
        assert national["status"] == "DRAFT"
        assert national["originating_match_candidate_id"] == candidate_id
        assert len(draft["mappings"]) == 2
        assert {m["source_material_id"] for m in draft["mappings"]} == source_ids
        assert all(m["approval_status"] == "PENDING_L1" for m in draft["mappings"])

        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(NationalMaterial)) == 1
            assert db.scalar(select(func.count()).select_from(MaterialMapping)) == 2

        st, detail = asyncio.run(make_request(app, "GET", f"/api/national-materials/{code}"))
        assert st == 200, f"national detail failed: {st}, {detail}"
        assert detail["national_material"]["national_material_code"] == code
        assert detail["national_material"]["status"] == "DRAFT"
        assert len(detail["mappings"]) == 2

        one_source = next(iter(source_ids))
        st, source_mappings = asyncio.run(make_request(app, "GET", f"/api/mappings/source/{one_source}"))
        assert st == 200, f"source mappings failed: {st}, {source_mappings}"
        assert len(source_mappings) == 1
        assert source_mappings[0]["national_material_code"] == code
        assert source_mappings[0]["national_material_status"] == "DRAFT"

        st, draft_2 = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}"))
        assert st == 200
        assert draft_2["idempotent_replay"] is True
        assert draft_2["national_material"]["national_material_code"] == code
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(NationalMaterial)) == 1
            assert db.scalar(select(func.count()).select_from(MaterialMapping)) == 2

        unknown = uuid.uuid4()
        st, _ = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{unknown}"))
        assert st == 404
        st, _ = asyncio.run(make_request(app, "GET", "/api/national-materials/NAMM-UNKNOWN-CODE"))
        assert st == 404
        st, _ = asyncio.run(make_request(app, "GET", f"/api/mappings/source/{unknown}"))
        assert st == 404

        engine.dispose()

    print("PASS Prompt 5 national material registry verified: DRAFT code, two mappings, idempotency, retrieval, 404s.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 5 verification failed: {exc}", file=sys.stderr)
        raise
