"""
Prompt 7 verification: persistent append-only, hash-chained audit ledger.

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


def post_json(app, path: str, payload: dict):
    body, content_type = json_body(payload)
    return asyncio.run(make_request(app, "POST", path, body, [(b"content-type", content_type.encode())]))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt7_") as tmp:
        db_path = Path(tmp) / "verify_prompt7.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import select, update

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import AuditEvent, MatchCandidate
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        csv_a = """item_code,description,uom,category,manufacturer
AUD-BRG-6205-A,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF
"""
        csv_b = """item_code,description,uom,category,manufacturer
AUD-BRG-6205-B,BALL BEARING 6205-2RS DEEP GROOVE SKF,NOS,BEARINGS,SKF
"""
        body_a, type_a = upload_body(csv_a, "AUDIT_CPSE_A", "audit_a.csv")
        st, ingest_a = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_a, [(b"content-type", type_a.encode())]))
        assert st == 200, f"ingest A failed: {st}, {ingest_a}"

        body_b, type_b = upload_body(csv_b, "AUDIT_CPSE_B", "audit_b.csv")
        st, ingest_b = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_b, [(b"content-type", type_b.encode())]))
        assert st == 200, f"ingest B failed: {st}, {ingest_b}"
        batch_b = ingest_b["batch"]["id"]

        run_body, run_type = json_body({"min_score": 0.65})
        st, run = asyncio.run(make_request(app, "POST", f"/api/matching/run/{batch_b}", run_body, [(b"content-type", run_type.encode())]))
        assert st == 200 and run["candidate_count"] >= 1, f"matching failed: {st}, {run}"

        with SessionLocal() as db:
            candidate = db.execute(select(MatchCandidate).order_by(MatchCandidate.hybrid_score.desc())).scalars().first()
            assert candidate is not None
            candidate_id = str(candidate.id)

        st, draft = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}"))
        assert st == 200, f"draft failed: {st}, {draft}"
        national_code = draft["national_material"]["national_material_code"]

        st, case_create = asyncio.run(make_request(app, "POST", f"/api/approvals/cases/from-national-material/{national_code}"))
        assert st == 200, f"case create failed: {st}, {case_create}"
        case_id = case_create["case"]["id"]

        st, l1 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Audit path L1 verification.",
        })
        assert st == 200, f"L1 failed: {st}, {l1}"

        st, l2 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Audit path L2 publication.",
        })
        assert st == 200, f"L2 failed: {st}, {l2}"

        st, events_page = asyncio.run(make_request(app, "GET", "/api/audit/events?page=1&limit=5"))
        assert st == 200, f"events page failed: {st}, {events_page}"
        assert events_page["count"] == 5
        assert events_page["total"] >= 10
        assert events_page["items"][0]["sequence_number"] == 1

        st, draft_events = asyncio.run(make_request(app, "GET", "/api/audit/events?action=NATIONAL_MATERIAL_DRAFT_CREATED"))
        assert st == 200 and draft_events["total"] == 1
        national_id = draft_events["items"][0]["entity_id"]

        st, national_events = asyncio.run(make_request(app, "GET", f"/api/audit/events?entity_type=national_material&entity_id={national_id}"))
        assert st == 200 and national_events["total"] >= 2

        st, verify_ok = asyncio.run(make_request(app, "POST", "/api/audit/verify"))
        assert st == 200, f"verify intact failed: {st}, {verify_ok}"
        assert verify_ok["status"] == "CHAIN_INTACT"
        assert verify_ok["verified_events"] == verify_ok["total_events"]

        actions = {event["action"] for event in asyncio.run(make_request(app, "GET", "/api/audit/events?page=1&limit=200"))[1]["items"]}
        expected_actions = {
            "MATERIALS_INGESTED",
            "MATCHING_RUN_COMPLETED",
            "NATIONAL_MATERIAL_DRAFT_CREATED",
            "APPROVAL_CASE_CREATED",
            "APPROVAL_L1_APPROVED",
            "APPROVAL_L2_APPROVED",
            "MATERIAL_MAPPINGS_STATUS_CHANGED",
            "NATIONAL_MATERIAL_PUBLISHED",
        }
        missing = expected_actions - actions
        assert not missing, f"missing audit actions: {missing}"

        with SessionLocal() as db:
            db.execute(
                update(AuditEvent)
                .where(AuditEvent.sequence_number == 2)
                .values(reason="tampered without recomputing hash")
            )
            db.commit()

        st, verify_bad = asyncio.run(make_request(app, "POST", "/api/audit/verify"))
        assert st == 409, f"tampered verify should return 409: {st}, {verify_bad}"
        assert verify_bad["status"] == "CHAIN_BROKEN"
        assert verify_bad["first_broken_sequence"] == 2

        st, demo_trail = asyncio.run(make_request(app, "GET", "/api/audit/demo-trail"))
        assert st == 200 and demo_trail["total_events"] >= 1
        st, demo_verify = asyncio.run(make_request(app, "POST", "/api/audit/demo-verify"))
        assert st == 200 and demo_verify["chain_status"] == "CHAIN_INTACT"

        engine.dispose()

    print("PASS Prompt 7 persistent audit ledger verified: events, filters, intact chain, tamper detection, demo compatibility.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 7 verification failed: {exc}", file=sys.stderr)
        raise
