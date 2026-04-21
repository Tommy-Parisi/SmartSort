"""
Local license validation for FileSort.

License keys are UUID4 strings delivered via Gumroad purchase.
Validation is purely local — no network call required after activation.

Trial mode: fully functional, capped at TRIAL_FILE_LIMIT files per sort.
Licensed: unlimited.

~/.smartsort/license.key  — one line, the UUID4 key
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

SMARTSORT_DIR = Path.home() / ".smartsort"
LICENSE_PATH = SMARTSORT_DIR / "license.key"
TRIAL_FILE_LIMIT = 500


def _read_raw() -> str:
    try:
        return LICENSE_PATH.read_text().strip()
    except Exception:
        return ""


def _valid_uuid4(key: str) -> bool:
    try:
        val = uuid.UUID(key, version=4)
        return str(val) == key.lower()
    except Exception:
        return False


def is_licensed() -> bool:
    """Return True if a valid UUID4 license key is present on disk."""
    return _valid_uuid4(_read_raw())


def activate(key: str) -> bool:
    """
    Write a license key to disk.
    Returns True on success, False if the key is not a valid UUID4.
    """
    key = key.strip().lower()
    if not _valid_uuid4(key):
        return False
    SMARTSORT_DIR.mkdir(parents=True, exist_ok=True)
    LICENSE_PATH.write_text(key)
    return True


def deactivate() -> None:
    """Remove the license key (resets to trial mode)."""
    try:
        LICENSE_PATH.unlink()
    except FileNotFoundError:
        pass


def check_file_limit(file_count: int) -> dict:
    """
    Check whether a sort of file_count files is permitted.

    Returns:
        {
            "allowed":   bool,
            "licensed":  bool,
            "limit":     int | None,   # None when licensed (no cap)
            "count":     int,
        }
    """
    licensed = is_licensed()
    if licensed:
        return {"allowed": True, "licensed": True, "limit": None, "count": file_count}
    return {
        "allowed": file_count <= TRIAL_FILE_LIMIT,
        "licensed": False,
        "limit": TRIAL_FILE_LIMIT,
        "count": file_count,
    }


def license_status() -> dict:
    """Summary dict for frontend display."""
    licensed = is_licensed()
    return {
        "licensed": licensed,
        "key": _read_raw() if licensed else None,
        "trial_limit": TRIAL_FILE_LIMIT,
    }
