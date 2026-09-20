"""
Prompt 6 verification: durable L1/L2 approval workflow.

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


def create_case(app, SessionLocal, MatchCandidate, NationalMaterial, scenario: str):
    from sqlalchemy import select

    bearing_by_scenario = {
        "approve": ("6205", "2RS", "C3"),
        "reject": ("6305", "ZZ", "C3"),
        "info": ("6204", "2RS", "C0"),
    }
    bearing_number, seal, clearance = bearing_by_scenario.get(scenario, ("6206", "ZZ", "C3"))
    left_code = f"{scenario.upper()}-A-{uuid.uuid4().hex[:6]}"
    right_code = f"{scenario.upper()}-B-{uuid.uuid4().hex[:6]}"
    csv_a = f"""item_code,description,uom,category,manufacturer
{left_code},DEEP GROOVE BALL BEARING {bearing_number} {seal} {clearance} SKF,NOS,BEARINGS,SKF
"""
    csv_b = f"""item_code,description,uom,category,manufacturer
{right_code},BALL BEARING {bearing_number}-{seal} DEEP GROOVE SKF,NOS,BEARINGS,SKF
"""
    body_a, type_a = upload_body(csv_a, f"{scenario}_CPSE_A", f"{scenario}_a.csv")
    st, _ = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_a, [(b"content-type", type_a.encode())]))
    assert st == 200

    body_b, type_b = upload_body(csv_b, f"{scenario}_CPSE_B", f"{scenario}_b.csv")
    st, ingest_b = asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body_b, [(b"content-type", type_b.encode())]))
    assert st == 200
    batch_b = ingest_b["batch"]["id"]

    run_body, run_type = json_body({"min_score": 0.65})
    st, run = asyncio.run(make_request(app, "POST", f"/api/matching/run/{batch_b}", run_body, [(b"content-type", run_type.encode())]))
    assert st == 200 and run["candidate_count"] >= 1

    with SessionLocal() as db:
        candidate = db.execute(
            select(MatchCandidate)
            .outerjoin(NationalMaterial, NationalMaterial.originating_match_candidate_id == MatchCandidate.id)
            .where(NationalMaterial.id.is_(None))
            .order_by(MatchCandidate.created_at.desc(), MatchCandidate.hybrid_score.desc())
        ).scalars().first()
        assert candidate is not None
        candidate_id = str(candidate.id)

    st, draft = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}"))
    assert st == 200, f"draft failed: {st}, {draft}"
    code = draft["national_material"]["national_material_code"]

    st, case = asyncio.run(make_request(app, "POST", f"/api/approvals/cases/from-national-material/{code}"))
    assert st == 200, f"case create failed: {st}, {case}"
    assert case["case"]["current_stage"] == "PENDING_L1"
    assert case["case"]["approval_status"] == "PENDING"
    assert case["case"]["actor_identity_verified"] is True
    return case["case"]["id"], code


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt6_") as tmp:
        db_path = Path(tmp) / "verify_prompt6.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"

        from alembic import command
        from alembic.config import Config
        from sqlalchemy import select

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.db.models import ApprovalCase, MaterialMapping, MatchCandidate, NationalMaterial
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        case_id, national_code = create_case(app, SessionLocal, MatchCandidate, NationalMaterial, "approve")

        st, replay = asyncio.run(make_request(app, "POST", f"/api/approvals/cases/from-national-material/{national_code}"))
        assert st == 200
        assert replay["idempotent_replay"] is True
        assert replay["case"]["id"] == case_id

        st, l1 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Technical parameters verified.",
        })
        assert st == 200, f"L1 approve failed: {st}, {l1}"
        assert l1["case"]["current_stage"] == "PENDING_L2"
        assert all(m["approval_status"] == "PENDING_L2" for m in l1["case"]["mappings"])

        st, l2 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Approved for national publication.",
        })
        assert st == 200, f"L2 approve failed: {st}, {l2}"
        assert l2["case"]["current_stage"] == "APPROVED"
        assert l2["case"]["approval_status"] == "APPROVED"
        assert l2["case"]["national_material"]["status"] == "ACTIVE"
        assert l2["case"]["national_material"]["approved_by"] == "Verify Admin"
        assert all(m["approval_status"] == "APPROVED" for m in l2["case"]["mappings"])
        assert all(m["reviewer_id"] == "Verify Admin" for m in l2["case"]["mappings"])
        assert all(m["reviewed_at"] for m in l2["case"]["mappings"])

        with SessionLocal() as db:
            persisted = db.get(ApprovalCase, uuid.UUID(case_id))
            national = db.get(NationalMaterial, persisted.proposed_national_material_id)
            mappings = db.execute(
                select(MaterialMapping).where(MaterialMapping.national_material_id == national.id)
            ).scalars().all()
            candidate = db.get(MatchCandidate, persisted.match_candidate_id)
            assert persisted.approval_status == "APPROVED"
            assert national.status == "ACTIVE"
            assert national.approved_by == "Verify Admin"
            assert len(mappings) == 2 and all(m.approval_status == "APPROVED" for m in mappings)
            assert candidate.status == "APPROVED"

        st, terminal = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "REJECT",
        })
        assert st == 409, f"terminal decision should fail: {st}, {terminal}"

        reject_case_id, _ = create_case(app, SessionLocal, MatchCandidate, NationalMaterial, "reject")
        st, rejected = post_json(app, f"/api/approvals/cases/{reject_case_id}/decision", {
            "decision": "REJECT",
            "reviewer_note": "Specifications are materially different.",
        })
        assert st == 200, f"L1 reject failed: {st}, {rejected}"
        assert rejected["case"]["current_stage"] == "REJECTED"
        assert rejected["case"]["approval_status"] == "REJECTED"
        assert rejected["case"]["national_material"]["status"] == "REJECTED"
        assert all(m["approval_status"] == "REJECTED" for m in rejected["case"]["mappings"])

        info_case_id, _ = create_case(app, SessionLocal, MatchCandidate, NationalMaterial, "info")
        st, needs_info = post_json(app, f"/api/approvals/cases/{info_case_id}/decision", {
            "decision": "NEEDS_MORE_INFO",
            "reviewer_note": "Need drawing and make equivalence.",
        })
        assert st == 200, f"needs info failed: {st}, {needs_info}"
        assert needs_info["case"]["current_stage"] == "NEEDS_MORE_INFO"
        assert all(m["approval_status"] == "NEEDS_MORE_INFO" for m in needs_info["case"]["mappings"])

        st, resubmitted = post_json(app, f"/api/approvals/cases/{info_case_id}/resubmit", {
            "submitter_note": "Drawing reference and equivalence note attached.",
        })
        assert st == 200, f"resubmit failed: {st}, {resubmitted}"
        assert resubmitted["case"]["current_stage"] == "PENDING_L1"
        assert resubmitted["case"]["approval_status"] == "PENDING"
        assert resubmitted["case"]["l1_decision"] == "NEEDS_MORE_INFO"
        assert all(m["approval_status"] == "PENDING_L1" for m in resubmitted["case"]["mappings"])

        st, queue = asyncio.run(make_request(app, "GET", "/api/approvals/cases?current_stage=PENDING_L1"))
        assert st == 200 and queue["total"] >= 1
        st, detail = asyncio.run(make_request(app, "GET", f"/api/approvals/cases/{info_case_id}"))
        assert st == 200 and detail["id"] == info_case_id

        st, demo_queue = asyncio.run(make_request(app, "GET", "/api/approvals/demo-queue"))
        assert st == 200 and demo_queue["total_cases"] >= 1
        demo_payload = {
            "approval_case_id": demo_queue["cases"][0]["approval_case_id"],
            "decision": "APPROVE",
            "reviewer_name": "Demo Reviewer",
            "reviewer_role": "L1_NODAL_OFFICER",
            "reviewer_note": "Demo route compatibility check.",
            "stage": "L1_REVIEW",
        }
        st, demo_action = post_json(app, "/api/approvals/demo-action", demo_payload)
        assert st == 200 and demo_action["persisted"] is False

        engine.dispose()

    print("PASS Prompt 6 persistent approvals verified: case idempotency, L1/L2 transitions, rejection, needs-info resubmit, demo compatibility.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 6 verification failed: {exc}", file=sys.stderr)
        raise
