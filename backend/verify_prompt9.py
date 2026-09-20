"""
Prompt 9 verification: production analytics APIs and live dashboard data contract.

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


def upload_csv(app, *, cpse: str, filename: str, csv_text: str):
    body, content_type = multipart_body(
        {"source_cpse": cpse, "source_system": "PROMPT9_VERIFY_ERP"},
        "file",
        filename,
        csv_text.encode("utf-8"),
    )
    return asyncio.run(make_request(app, "POST", "/api/materials/ingest-csv", body, [(b"content-type", content_type.encode())]))


def by_cpse(summary: dict, cpse: str) -> dict:
    return next((item for item in summary["cpse_breakdown"] if item["cpse_name"] == cpse), {})


def by_category(summary: dict, category: str) -> dict:
    return next((item for item in summary["category_breakdown"] if item["category"] == category), {})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="namm_prompt9_") as tmp:
        db_path = Path(tmp) / "verify_prompt9.db"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ["EMBEDDING_PROVIDER"] = "stub"
        os.environ["EMBEDDING_DIMENSIONS"] = "64"
        os.environ["EMBEDDING_ALLOW_STUB_FALLBACK"] = "true"

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(alembic_cfg, "head")

        from app.core.config import settings
        from app.db.session import SessionLocal, engine
        from main import app
        install_verify_admin(SessionLocal)

        settings.EMBEDDING_PROVIDER = "stub"
        settings.EMBEDDING_DIMENSIONS = 64
        settings.EMBEDDING_ALLOW_STUB_FALLBACK = True

        st, empty = asyncio.run(make_request(app, "GET", "/api/analytics/summary"))
        assert st == 200, f"empty analytics failed: {st}, {empty}"
        assert empty["total_source_materials"] == 0
        assert empty["total_ingestion_batches"] == 0
        assert empty["total_match_candidates"] == 0
        assert empty["duplicate_candidate_count"] == 0
        assert empty["approved_mapping_count"] == 0
        assert empty["audit_event_count"] == 0
        assert empty["audit_chain"]["last_sequence_number"] == 0
        assert empty["cpse_breakdown"] == []
        assert empty["category_breakdown"] == []
        assert empty["recent_activity"] == []
        assert empty["ingestion_timeline"] == []

        for invalid_path in ["/api/analytics/summary?days=0", "/api/analytics/summary?days=366"]:
            st, invalid = asyncio.run(make_request(app, "GET", invalid_path))
            assert st == 422, f"days validation should reject {invalid_path}: {st}, {invalid}"

        csv_a = """item_code,description,uom,category,manufacturer
ANL-BRG-6205-A,DEEP GROOVE BALL BEARING 6205 2RS C3 SKF,NOS,BEARINGS,SKF
"""
        st, ingest_a = upload_csv(app, cpse="ANALYTICS_CPSE_A", filename="analytics_a.csv", csv_text=csv_a)
        assert st == 200, f"first ingest failed: {st}, {ingest_a}"
        batch_a = ingest_a["batch"]["id"]

        csv_b = """item_code,description,uom,category,manufacturer
ANL-BRG-6205-B,BALL BEARING 6205-2RS DEEP GROOVE SKF,NOS,BEARINGS,SKF
"""
        st, ingest_b = upload_csv(app, cpse="ANALYTICS_CPSE_B", filename="analytics_b.csv", csv_text=csv_b)
        assert st == 200, f"second ingest failed: {st}, {ingest_b}"
        batch_b = ingest_b["batch"]["id"]

        st, run = post_json(app, f"/api/matching/run/{batch_b}", {"min_score": 0.55})
        assert st == 200, f"persistent matching failed: {st}, {run}"
        assert run["candidate_count"] >= 1

        st, results = asyncio.run(make_request(app, "GET", f"/api/matching/results/{batch_b}"))
        assert st == 200 and results["items"], f"matching results missing: {st}, {results}"
        candidate_id = results["items"][0]["id"]

        st, draft = asyncio.run(make_request(app, "POST", f"/api/national-materials/draft-from-candidate/{candidate_id}"))
        assert st == 200, f"draft creation failed: {st}, {draft}"
        national_code = draft["national_material"]["national_material_code"]
        assert draft["national_material"]["status"] == "DRAFT"
        assert len(draft["mappings"]) == 2

        st, case_create = asyncio.run(make_request(app, "POST", f"/api/approvals/cases/from-national-material/{national_code}"))
        assert st == 200, f"approval case creation failed: {st}, {case_create}"
        case_id = case_create["case"]["id"]
        assert case_create["case"]["current_stage"] == "PENDING_L1"

        st, l1 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Verified duplicate bearing records for analytics verification.",
        })
        assert st == 200, f"L1 approval failed: {st}, {l1}"
        assert l1["case"]["current_stage"] == "PENDING_L2"

        st, l2 = post_json(app, f"/api/approvals/cases/{case_id}/decision", {
            "decision": "APPROVE",
            "reviewer_note": "Approved national material publication for analytics verification.",
        })
        assert st == 200, f"L2 approval failed: {st}, {l2}"
        assert l2["case"]["approval_status"] == "APPROVED"
        assert l2["case"]["national_material"]["status"] == "ACTIVE"

        st, summary = asyncio.run(make_request(app, "GET", "/api/analytics/summary?days=30"))
        assert st == 200, f"analytics summary failed: {st}, {summary}"
        assert summary["days"] == 30
        assert summary["total_source_materials"] == 2
        assert summary["total_ingestion_batches"] == 2
        assert summary["batches_completed"] == 2
        assert summary["batches_with_errors"] == 0
        assert summary["total_match_candidates"] >= 1
        assert summary["duplicate_candidate_count"] >= 1
        assert summary["candidate_counts_by_status"].get("APPROVED", 0) >= 1
        assert summary["pending_l1_count"] == 0
        assert summary["pending_l2_count"] == 0
        assert summary["needs_more_info_count"] == 0
        assert summary["approved_mapping_count"] == 2
        assert summary["rejected_mapping_count"] == 0
        assert summary["national_material_draft_count"] == 0
        assert summary["national_material_active_count"] == 1
        assert summary["national_material_rejected_count"] == 0
        assert summary["estimated_approved_savings_inr"] > 0
        assert summary["audit_event_count"] > 0
        assert summary["audit_chain"]["last_sequence_number"] == summary["audit_event_count"]
        assert summary["audit_chain"]["last_hash"] != "0" * 64

        cpse_a = by_cpse(summary, "ANALYTICS_CPSE_A")
        cpse_b = by_cpse(summary, "ANALYTICS_CPSE_B")
        assert cpse_a["material_count"] == 1 and cpse_b["material_count"] == 1
        assert cpse_a["batch_count"] == 1 and cpse_b["batch_count"] == 1
        assert cpse_a["candidate_involvement_count"] >= 1 and cpse_b["candidate_involvement_count"] >= 1
        assert cpse_a["approved_mapping_count"] == 1 and cpse_b["approved_mapping_count"] == 1

        category = by_category(summary, "BEARINGS")
        assert category["material_count"] == 2
        assert category["candidate_involvement_count"] >= 1
        assert category["active_national_material_count"] == 1

        assert summary["ingestion_timeline"], "ingestion timeline should include current batches"
        assert sum(point["batches_created"] for point in summary["ingestion_timeline"]) == 2
        assert sum(point["source_materials_processed"] for point in summary["ingestion_timeline"]) == 2

        assert summary["recent_activity"], "recent activity should include durable audit events"
        timestamps = [event["timestamp"] for event in summary["recent_activity"]]
        assert timestamps == sorted(timestamps), "recent activity should be chronological"
        actions = {event["action"] for event in summary["recent_activity"]}
        assert "NATIONAL_MATERIAL_PUBLISHED" in actions
        assert not any("sample" in event["summary"].lower() for event in summary["recent_activity"])

        st, seven_day = asyncio.run(make_request(app, "GET", "/api/analytics/summary?days=7"))
        assert st == 200 and seven_day["days"] == 7

        engine.dispose()

    print(
        "PASS Prompt 9 analytics verified: empty database zeros, durable workflow counts, "
        "breakdowns, timeline, recent activity, audit-chain metadata, days validation, and no sample-data fallback."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 9 verification failed: {exc}", file=sys.stderr)
        raise
