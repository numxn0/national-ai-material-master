"""
Explicit local development user bootstrap.

Example:
  $env:NAMM_BOOTSTRAP_USERNAME="admin"
  $env:NAMM_BOOTSTRAP_PASSWORD="change-me-locally"
  $env:NAMM_BOOTSTRAP_DISPLAY_NAME="Local Admin"
  $env:NAMM_BOOTSTRAP_ROLES="ADMIN,AUDITOR"
  .\backend\.venv\Scripts\python.exe .\backend\seed_local_users.py
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.services.auth import create_or_update_local_user, user_roles


def main() -> int:
    username = os.getenv("NAMM_BOOTSTRAP_USERNAME", "").strip()
    password = os.getenv("NAMM_BOOTSTRAP_PASSWORD", "")
    display_name = os.getenv("NAMM_BOOTSTRAP_DISPLAY_NAME", username).strip() or username
    roles = [role.strip() for role in os.getenv("NAMM_BOOTSTRAP_ROLES", "").split(",") if role.strip()]
    organization_scope = os.getenv("NAMM_BOOTSTRAP_ORGANIZATION_SCOPE") or None

    if not username or not password or not roles:
        print(
            "Set NAMM_BOOTSTRAP_USERNAME, NAMM_BOOTSTRAP_PASSWORD, and NAMM_BOOTSTRAP_ROLES before running.",
            file=sys.stderr,
        )
        return 2

    with SessionLocal() as db:
        user = create_or_update_local_user(
            db,
            username=username,
            password=password,
            display_name=display_name,
            roles=roles,
            organization_scope=organization_scope,
        )
        print(
            f"Created/updated local user '{user.username}' with roles {', '.join(user_roles(user))}. "
            "Plaintext password was not stored."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
