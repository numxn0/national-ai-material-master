"""
Prompt 4 verification: persistent material matching.

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
    with tempfile.TemporaryDirectory(prefix="namm_prompt4_") as tmp:
        db_path = Path(tmp) / "verify_prompt4.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import func, select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import MatchCandidate, SourceMaterial
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        csv_a = """item_code,description,uom,category,manufacturer
RAIL-BRG-6205,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF
RAIL-CBL-10,CONTROL CABLE COPPER 2 CORE 1.5 SQMM,MTR,ELECTRICAL_CABLES,FINOLEX
"""
        csv_b = """item_code,description,uom,category,manufacturer
BHEL-BRG-6205,BALL BEARING 6205-2RS DEEP GROOVE SKF,NOS,BEARINGS,SKF
BHEL-VLV-50,BALL VALVE 50MM SS304 PN16,NOS,VALVES,L&T
"""

        body_a, type_a = upload_body(csv_a, "RAILWAYS", "rail_batch.csv")
        st, ingest_a = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/ingest-csv",
            body_a,
            [(b"content-type", type_a.encode())],
        ))
        assert st == 200, f"batch A ingest failed: {st}, {ingest_a}"

        body_b, type_b = upload_body(csv_b, "BHEL", "bhel_batch.csv")
        st, ingest_b = asyncio.run(make_request(
            app,
            "POST",
            "/api/materials/ingest-csv",
            body_b,
            [(b"content-type", type_b.encode())],
        ))
        assert st == 200, f"batch B ingest failed: {st}, {ingest_b}"
        batch_b = ingest_b["batch"]["id"]

        run_body, run_type = json_body({"min_score": 0.65})
        st, run_1 = asyncio.run(make_request(
            app,
            "POST",
            f"/api/matching/run/{batch_b}",
            run_body,
            [(b"content-type", run_type.encode())],
        ))
        assert st == 200, f"matching run failed: {st}, {run_1}"
        assert run_1["candidate_count"] >= 1
        assert run_1["created_count"] >= 1
        assert run_1["updated_count"] == 0

        with SessionLocal() as db:
            total_candidates = db.scalar(select(func.count()).select_from(MatchCandidate))
            assert total_candidates == run_1["created_count"]
            candidate = db.execute(select(MatchCandidate).order_by(MatchCandidate.hybrid_score.desc())).scalars().first()
            assert candidate is not None
            assert candidate.source_material_a_id is not None
            assert candidate.source_material_b_id is not None
            mat_a = db.get(SourceMaterial, candidate.source_material_a_id)
            mat_b = db.get(SourceMaterial, candidate.source_material_b_id)
            assert {mat_a.ingestion_batch_id, mat_b.ingestion_batch_id} == {
                uuid.UUID(ingest_a["batch"]["id"]),
                uuid.UUID(batch_b),
            }
            assert candidate.hybrid_score is not None and candidate.hybrid_score >= 0.65
            assert candidate.classification is not None
            assert candidate.method_version == "candidate-rules-v1 + hybrid-rule-v1 + explainability-v1"
            assert candidate.explanation.get("reviewer_summary")
            assert candidate.score_details.get("feature_vector")
            bhel_materials = db.execute(
                select(SourceMaterial).where(SourceMaterial.ingestion_batch_id == batch_b)
            ).scalars().all()
            assert any(m.match_status == "CANDIDATES_GENERATED" for m in bhel_materials)

        query = urlencode({"page": 1, "limit": 10, "min_hybrid_score": 0.65})
        st, results = asyncio.run(make_request(app, "GET", f"/api/matching/results/{batch_b}?{query}"))
        assert st == 200, f"matching results failed: {st}, {results}"
        assert results["total"] >= 1
        first = results["items"][0]
        assert first["source_material_a"] and first["source_material_b"]
        assert first["method_version"] == "candidate-rules-v1 + hybrid-rule-v1 + explainability-v1"

        st, run_2 = asyncio.run(make_request(
            app,
            "POST",
            f"/api/matching/run/{batch_b}",
            run_body,
            [(b"content-type", run_type.encode())],
        ))
        assert st == 200, f"second matching run failed: {st}, {run_2}"
        assert run_2["created_count"] == 0
        assert run_2["updated_count"] >= 1
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(MatchCandidate)) == total_candidates

        st, sample = asyncio.run(make_request(app, "GET", "/api/matching/candidates/sample?min_score=0.65"))
        assert st == 200 and sample["candidate_count"] >= 1, f"demo sample endpoint regressed: {st}, {sample}"

        engine.dispose()

    print("PASS Prompt 4 persistent matching verified: durable candidates, run/results APIs, idempotent upsert, material status updates, demo endpoint regression.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 4 verification failed: {exc}", file=sys.stderr)
        raise
