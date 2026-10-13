#!/usr/bin/env python3
"""Initialize local security storage and an administrator without default credentials."""

import os
from pathlib import Path

from lexecon.security.audit_service import AuditService
from lexecon.security.auth_service import AuthService, Role
from lexecon.security.signature_service import SignatureService


def main() -> None:
    password = os.environ.get("LEXECON_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("Set LEXECON_ADMIN_PASSWORD before running setup_security.py")

    data_dir = Path(os.environ.get("LEXECON_DATA_DIR", "."))
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    auth = AuthService(str(data_dir / "lexecon_auth.db"))
    AuditService(str(data_dir / "lexecon_export_audit.db"))
    SignatureService(str(data_dir / "lexecon_keys"))

    username = os.environ.get("LEXECON_ADMIN_USERNAME", "admin")
    email = os.environ.get("LEXECON_ADMIN_EMAIL", "admin@example.local")
    try:
        auth.create_user(username, email, password, Role.ADMIN, "Administrator")
    except ValueError as error:
        raise SystemExit(f"Administrator setup failed: {error}") from error
    print(f"Security storage initialized; administrator: {username}")


if __name__ == "__main__":
    main()
