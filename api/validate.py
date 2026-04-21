"""
Vercel serverless function — /api/validate

Two roles:
  1. Gumroad purchase webhook (POST from Gumroad on sale):
       Receives sale data, generates a UUID4 license key, returns it.
       Gumroad can include this key in the buyer's receipt via a custom
       "Generate a unique key" product setting — or we return it here
       and Gumroad forwards it in the confirmation email.

  2. Key format check (POST from the app, optional):
       Body: {"license_key": "<uuid4>"}
       Returns: {"valid": true/false}
       The app currently validates locally, but this endpoint exists
       for a future revocation check.

Deploy:
    vercel deploy  (from repo root — vercel.json picks up api/)

Environment variables (set in Vercel dashboard):
    GUMROAD_PRODUCT_ID   — your Gumroad product permalink/id
    WEBHOOK_SECRET       — optional shared secret for webhook auth
"""

from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler


GUMROAD_PRODUCT_ID = os.environ.get("GUMROAD_PRODUCT_ID", "")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")


def _generate_key() -> str:
    return str(uuid.uuid4())


def _is_valid_uuid4(key: str) -> bool:
    try:
        val = uuid.UUID(key.strip(), version=4)
        return str(val) == key.strip().lower()
    except Exception:
        return False


def _respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(request, context=None):
    """Vercel Python runtime entry point."""
    method = getattr(request, "method", "POST")
    body_bytes = getattr(request, "body", b"") or b""

    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except Exception:
        # Gumroad sends form-encoded — parse it
        from urllib.parse import parse_qs
        qs = parse_qs(body_bytes.decode("utf-8", errors="ignore"))
        payload = {k: v[0] for k, v in qs.items()}

    # ── Key format validation (app-side check) ────────────────────────────────
    if "license_key" in payload:
        key = str(payload["license_key"]).strip()
        return _respond(200, {"valid": _is_valid_uuid4(key), "license_key": key})

    # ── Gumroad purchase webhook ──────────────────────────────────────────────
    # Verify product if GUMROAD_PRODUCT_ID is configured
    if GUMROAD_PRODUCT_ID:
        incoming_id = payload.get("product_permalink") or payload.get("product_id", "")
        if incoming_id and incoming_id != GUMROAD_PRODUCT_ID:
            return _respond(400, {"error": "unknown product"})

    sale_id = payload.get("sale_id") or payload.get("id", "unknown")
    email = payload.get("email", "")

    license_key = _generate_key()

    return _respond(200, {
        "license_key": license_key,
        "sale_id": sale_id,
        "email": email,
        "message": (
            f"Your FileSort license key: {license_key}\n"
            "Copy this key and paste it into FileSort → Settings → Enter License Key."
        ),
    })
