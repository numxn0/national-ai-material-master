"""
Prompt 8 verification: pluggable persisted semantic embeddings.

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


def json_body(payload: dict):
    return json.dumps(payload).encode("utf-8"), "application/json"


def post_json(app, path: str, payload: dict):
    body, content_type = json_body(payload)
    return asyncio.run(make_request(app, "POST", path, body, [(b"content-type", content_type.encode())]))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt8_") as tmp:
        db_path = Path(tmp) / "verify_prompt8.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
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
        from app.db.models import MaterialEmbedding, MatchCandidate, SourceMaterial
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        settings.EMBEDDING_PROVIDER = "stub"
        settings.EMBEDDING_DIMENSIONS = 64
        settings.EMBEDDING_ALLOW_STUB_FALLBACK = True

        csv_text = """item_code,description,uom,category,manufacturer
EMB-BRG-6205-A,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF
EMB-BRG-6205-B,BALL BEARING 6205-2RS DEEP GROOVE SKF,NOS,BEARINGS,SKF
"""
        body, content_type = multipart_body(
            {"source_cpse": "EMBED_CPSE", "source_system": "VERIFY_ERP"},
            "file",
            "embeddings.csv",
            csv_text.encode("utf-8"),
        )
        st, ingest = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body, [(b"content-type", content_type.encode())]))
        assert st == 200, f"ingest failed: {st}, {ingest}"
        batch_id = ingest["batch"]["id"]

        st, generated = asyncio.run(make_request(app, "POST", f"/api/embeddings/generate/batch/{batch_id}"))
        assert st == 200, f"generate failed: {st}, {generated}"
        assert generated["provider"]["provider_requested"] == "stub"
        assert generated["provider"]["provider_used"] == "stub"
        assert generated["total_materials"] == 2
        assert generated["generated_count"] == 2
        assert all(item["dimensions"] == 64 for item in generated["items"])
        assert all(item["source_text_hash"] for item in generated["items"])

        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(MaterialEmbedding)) == 2
            source_ids = [str(row.id) for row in db.execute(select(SourceMaterial).order_by(SourceMaterial.source_material_code)).scalars().all()]

        st, generated_again = asyncio.run(make_request(app, "POST", f"/api/embeddings/generate/batch/{batch_id}"))
        assert st == 200
        assert generated_again["reused_count"] == 2
        with SessionLocal() as db:
            assert db.scalar(select(func.count()).select_from(MaterialEmbedding)) == 2

        st, meta = asyncio.run(make_request(app, "GET", f"/api/embeddings/material/{source_ids[0]}"))
        assert st == 200 and meta["source_material_id"] == source_ids[0]

        st, compare = post_json(app, "/api/embeddings/compare", {
            "source_material_a_id": source_ids[0],
            "source_material_b_id": source_ids[1],
        })
        assert st == 200, f"compare failed: {st}, {compare}"
        assert 0.0 <= compare["semantic_similarity_score"] <= 1.0
        assert compare["embedding_a"]["status"] == "reused"
        assert compare["embedding_b"]["status"] == "reused"

        run_body, run_type = json_body({"min_score": 0.65})
        st, run = asyncio.run(make_request(app, "POST", f"/api/matching/run/{batch_id}", run_body, [(b"content-type", run_type.encode())]))
        assert st == 200 and run["candidate_count"] >= 1, f"matching failed: {st}, {run}"
        with SessionLocal() as db:
            candidate = db.execute(select(MatchCandidate).order_by(MatchCandidate.hybrid_score.desc())).scalars().first()
            assert candidate is not None
            semantic = (candidate.score_details or {}).get("persistent_semantic_embedding")
            assert semantic is not None
            assert 0.0 <= semantic["semantic_similarity_score"] <= 1.0
            assert semantic["provider"]["provider_used"] == "stub"
            assert semantic["decisive_scoring_signal"] is False

        settings.EMBEDDING_PROVIDER = "sentence_transformer"
        settings.SENTENCE_TRANSFORMER_MODEL = "__unavailable__verify_no_download"
        settings.EMBEDDING_ALLOW_STUB_FALLBACK = True
        st, fallback_compare = post_json(app, "/api/embeddings/compare", {
            "source_material_a_id": source_ids[0],
            "source_material_b_id": source_ids[1],
        })
        assert st == 200, f"fallback compare failed: {st}, {fallback_compare}"
        assert fallback_compare["provider"]["provider_requested"] == "sentence_transformer"
        assert fallback_compare["provider"]["provider_used"] == "stub"
        assert fallback_compare["provider"]["fallback_reason"]

        settings.EMBEDDING_ALLOW_STUB_FALLBACK = False
        st, fallback_disabled = post_json(app, "/api/embeddings/compare", {
            "source_material_a_id": source_ids[0],
            "source_material_b_id": source_ids[1],
        })
        assert st == 503, f"fallback disabled should fail with 503: {st}, {fallback_disabled}"

        st, legacy_generate = post_json(app, "/api/matching/embedding/generate", {
            "text": "DEEP GROOVE BALL BEARING 6205 2RS",
            "dimensions": 64,
        })
        assert st == 200 and legacy_generate["dimensions"] == 64
        st, legacy_sample = asyncio.run(make_request(app, "GET", "/api/matching/embedding/sample"))
        assert st == 200 and legacy_sample["total_comparisons"] >= 1

        engine.dispose()

    print("PASS Prompt 8 persistent embeddings verified: storage, reuse, comparison, matching metadata, fallback behavior, legacy endpoints.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 8 verification failed: {exc}", file=sys.stderr)
        raise
