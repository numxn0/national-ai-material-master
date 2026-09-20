"""
Prompt 11 verification: HTTP Basic auth, durable users/roles, and RBAC.

Uses a temporary SQLite database only.
"""

import asyncio
import base64
import json
import os
import shutil
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


def auth(username: str, password: str) -> list[tuple[bytes, bytes]]:
    token = base64.b64encode(f"{username}:{password}".encode("ascii")).decode("ascii")
    return [(b"authorization", f"Basic {token}".encode("ascii"))]


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


def post_json(app, path: str, payload: dict, headers: list[tuple[bytes, bytes]] | None = None):
    body = json.dumps(payload).encode("utf-8")
    merged = [(b"content-type", b"application/json")]
    if headers:
        merged.extend(headers)
    return asyncio.run(make_request(app, "POST", path, body, merged))


def upload_csv(app, *, cpse: str, code: str, desc: str, filename: str, headers):
    csv_text = f"""item_code,description,uom,category,manufacturer
{code},{desc},NOS,BEARINGS,SKF
"""
    body, content_type = multipart_body(
        {"source_cpse": cpse, "source_system": "RBAC_VERIFY_ERP"},
        "file",
        filename,
        csv_text.encode("utf-8"),
    )
    return asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body, [(b"content-type", content_type.encode()), *headers]))


def create_workflow(app, admin_headers, cpse_headers):
    st, _ = upload_csv(
        app,
        cpse="SCOPE_CPSE",
        code="RBAC-BRG-6205-A",
        desc="DEEP GROOVE BALL BEARING 6205 2RS C3 SKF",
        filename="rbac_a.csv",
        headers=admin_headers,
    )
    assert st == 200
    st, ingest_b = upload_csv(
        app,
        cpse="SCOPE_CPSE",
        code="RBAC-BRG-6205-B",
        desc="BALL BEARING 6205-2RS DEEP GROOVE SKF",
        filename="rbac_b.csv",
        headers=admin_headers,
    )
    assert st == 200
    batch_id = ingest_b["batch"]["id"]
    st, run = post_json(app, f"/api/matching/run/{batch_id}", {"min_score": 0.55}, admin_headers)
    assert st == 200 and run["candidate_count"] >= 1
    st, results = asyncio.run(make_request(app, "GET", f"/api/matching/results/{batch_id}"))
    assert st == 200 and results["items"]
    candidate_id = results["items"][0]["id"]
    st, draft = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}", headers=admin_headers))
    assert st == 200
    code = draft["national_material"]["national_material_code"]
    st, case = asyncio.run(make_request(app, "POST", f"/api/approvals/cases/from-national-material/{code}", headers=cpse_headers))
    assert st == 200, f"CPSE case create failed: {st}, {case}"
    assert case["actor_identity_verified"] is True
    return case["case"]["id"]


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="namm_prompt11_auth_")
    engine = None
    try:
        db_path = Path(tmp) / "verify_prompt11.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ["SAP_ODATA_MODE"] = "mock"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import AuditEvent
        from app.db.session import SessionLocal, engine as db_engine
        from app.services.auth import create_or_update_local_user
        from main import app

        engine = db_engine
        with SessionLocal() as db:
            create_or_update_local_user(db, username="admin", password="admin-pass", display_name="Admin User", roles=["ADMIN"], organization_scope=None)
            create_or_update_local_user(db, username="cpse", password="cpse-pass", display_name="CPSE User", roles=["CPSE_USER"], organization_scope="SCOPE_CPSE")
            create_or_update_local_user(db, username="l1", password="l1-pass", display_name="L1 Reviewer", roles=["L1_REVIEWER"], organization_scope=None)
            create_or_update_local_user(db, username="l2", password="l2-pass", display_name="L2 Authority", roles=["L2_AUTHORITY"], organization_scope=None)
            create_or_update_local_user(db, username="auditor", password="audit-pass", display_name="Audit User", roles=["AUDITOR"], organization_scope=None)

        admin_h = auth("admin", "admin-pass")
        cpse_h = auth("cpse", "cpse-pass")
        l1_h = auth("l1", "l1-pass")
        l2_h = auth("l2", "l2-pass")
        auditor_h = auth("auditor", "audit-pass")

        st, _ = asyncio.run(make_request(app, "GET", "/api/auth/me"))
        assert st == 401
        st, _ = asyncio.run(make_request(app, "GET", "/api/auth/me", headers=auth("admin", "wrong")))
        assert st == 401
        st, me = asyncio.run(make_request(app, "GET", "/api/auth/me", headers=cpse_h))
        assert st == 200 and me["username"] == "cpse" and me["roles"] == ["CPSE_USER"]
        assert "password" not in json.dumps(me).lower()

        st, _ = asyncio.run(make_request(app, "POST", "/api/approvals/cases/from-national-material/not-real"))
        assert st == 401

        st, scoped_reject = post_json(app, "/api/integrations/sap/import-materials", {
            "source_cpse": "OTHER_CPSE",
            "source_system": "SAP_SCOPE_TEST",
            "connection_name": "scope-test",
            "idempotency_key": "scope-test",
        }, cpse_h)
        assert st == 403, f"mismatched CPSE scope should be rejected: {st}, {scoped_reject}"

        case_id = create_workflow(app, admin_h, cpse_h)

        st, cpse_decision = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE"}, cpse_h)
        assert st == 403
        st, auditor_decision = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE"}, auditor_h)
        assert st == 403
        st, spoof = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE", "reviewer_name": "Client Spoof"}, l1_h)
        assert st == 400
        st, l1 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE", "reviewer_name": "L1 Reviewer"}, l1_h)
        assert st == 200 and l1["actor_identity_verified"] is True
        assert l1["case"]["l1_reviewer"] == "L1 Reviewer"
        assert l1["case"]["current_stage"] == "PENDING_L2"
        st, l1_l2 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE"}, l1_h)
        assert st == 403
        st, l2 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {"decision": "APPROVE"}, l2_h)
        assert st == 200 and l2["case"]["approval_status"] == "APPROVED"
        assert l2["case"]["l2_reviewer"] == "L2 Authority"

        st, events = asyncio.run(make_request(app, "GET", "/api/audit/events?page=1&limit=200", headers=auditor_h))
        assert st == 200 and events["total"] > 0
        st, verify = asyncio.run(make_request(app, "POST", "/api/audit/verify", headers=auditor_h))
        assert st == 200 and verify["status"] == "CHAIN_INTACT"
        st, auditor_create = asyncio.run(make_request(app, "POST", "/api/approvals/cases/from-national-material/not-real", headers=auditor_h))
        assert st == 403

        with SessionLocal() as db:
            actors = db.execute(select(AuditEvent.actor).where(AuditEvent.action.like("APPROVAL_%"))).scalars().all()
            assert "L1 Reviewer" in actors and "L2 Authority" in actors
            assert "Client Spoof" not in actors
            payloads = db.execute(select(AuditEvent.new_value).where(AuditEvent.action.in_(["APPROVAL_L1_APPROVED", "APPROVAL_L2_APPROVED"]))).scalars().all()
            assert all(payload.get("actor_identity_verified") is True for payload in payloads)

        st, demo_queue = asyncio.run(make_request(app, "GET", "/api/approvals/demo-queue"))
        assert st == 200 and demo_queue["total_cases"] >= 1
        st, demo_audit = asyncio.run(make_request(app, "GET", "/api/audit/demo-trail"))
        assert st == 200 and demo_audit["total_events"] >= 1

    finally:
        if engine is not None:
            engine.dispose()
        shutil.rmtree(tmp, ignore_errors=True)

    print("PASS Prompt 11 Basic Auth/RBAC verified: users, roles, 401/403, scoped CPSE, approval identity, audit access, demo compatibility.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 11 verification failed: {exc}", file=sys.stderr)
        raise
