from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_shared_contracts_are_up_to_date():
    """OpenAPI + golden fixtures must be regenerated whenever the API or the shared algorithms change."""
    r = subprocess.run(
        [sys.executable, "-m", "scripts.generate_contracts", "--check"], cwd=BACKEND, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_error_codes_file_matches_backend():
    import json

    from app.core.errors import RETRYABLE, STATUS_BY_CODE

    shared = json.loads((BACKEND.parent / "shared" / "api-contracts" / "error_codes.json").read_text())
    assert {e["code"]: e["httpStatus"] for e in shared["codes"]} == STATUS_BY_CODE
    assert {e["code"] for e in shared["codes"] if e["retryable"]} == RETRYABLE
