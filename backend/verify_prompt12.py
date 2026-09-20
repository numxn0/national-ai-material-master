"""
Prompt 12 verification: safe reproducible production demo runner.

Uses a temporary SQLite database only and validates destructive-operation guards.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent


def run_command(args: list[str], env: dict[str, str], expect_success: bool) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(f"command failed unexpectedly: {args}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    if not expect_success and result.returncode == 0:
        raise AssertionError(f"command succeeded unexpectedly: {args}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    return result


def extract_json_summary(stdout: str) -> dict:
    start = stdout.find("{")
    if start < 0:
        raise AssertionError(f"production demo did not print JSON summary:\n{stdout}")
    return json.loads(stdout[start:])


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="namm_prompt12_demo_")).resolve()
    outside = Path(tempfile.gettempdir()).resolve() / "namm_prompt12_outside.db"
    try:
        demo_db = tmp / "production_demo.db"
        demo_url = f"sqlite:///{demo_db.as_posix()}"
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": demo_url,
                "SAP_ODATA_MODE": "mock",
                "SAP_ODATA_ENTITY_SET": "A_Material",
                "EMBEDDING_PROVIDER": "stub",
                "EMBEDDING_ALLOW_STUB_FALLBACK": "true",
                "PYTHONPATH": str(BACKEND_DIR),
            }
        )

        result = run_command(
            [sys.executable, str(BACKEND_DIR / "run_production_demo.py"), "--database-url", demo_url, "--fresh"],
            env,
            expect_success=True,
        )
        summary = extract_json_summary(result.stdout)
        assert summary["national_material_status"] == "ACTIVE"
        assert summary["approved_mapping_count"] == 2
        assert summary["approval_case"]["approval_status"] == "APPROVED"
        assert summary["audit_chain"]["status"] == "CHAIN_INTACT"
        assert summary["audit_chain"]["event_count"] > 0
        assert summary["analytics_headline_counts"]["total_source_materials"] > 0
        assert summary["analytics_headline_counts"]["total_ingestion_batches"] >= 2
        assert summary["analytics_headline_counts"]["total_match_candidates"] > 0
        assert summary["analytics_headline_counts"]["national_material_active_count"] > 0

        unsafe_url = f"sqlite:///{outside.as_posix()}"
        unsafe = run_command(
            [sys.executable, str(BACKEND_DIR / "run_production_demo.py"), "--database-url", unsafe_url, "--fresh"],
            env,
            expect_success=False,
        )
        assert "--fresh refused" in unsafe.stderr or "FAIL production demo" in unsafe.stderr
        assert not outside.exists(), "unsafe --fresh rejection should not create or delete the outside database file"

        postgres = run_command(
            [
                sys.executable,
                str(BACKEND_DIR / "run_production_demo.py"),
                "--database-url",
                "postgresql+psycopg://demo:secret@example.invalid:5432/namm",
                "--fresh",
            ],
            env,
            expect_success=False,
        )
        assert "PostgreSQL" in postgres.stderr or "only supported for SQLite" in postgres.stderr
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if outside.exists():
            outside.unlink()

    print(
        "PASS Prompt 12 production demo verified: clean SQLite run, ACTIVE code, two approved mappings, "
        "APPROVED case, intact audit chain, analytics counts, and safe --fresh rejection paths."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL Prompt 12 verification failed: {exc}", file=sys.stderr)
        raise
