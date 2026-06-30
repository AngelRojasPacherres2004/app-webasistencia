from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from config.db import load_env
from supabase_backend import get_admin_by_email, verify_password


TOKEN_TTL_SECONDS = 60 * 60 * 12


def _secret() -> bytes:
    load_env()
    configured = os.getenv("AUTH_SECRET", "").strip()
    if configured:
        return configured.encode("utf-8")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return hashlib.sha256(database_url.encode("utf-8")).digest()
    return b"web-asistencia-local-secret"


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def create_token(username: str) -> str:
    payload = json.dumps(
        {
            "u": str(username or "").strip().lower(),
            "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = _encode(payload)
    signature = hmac.new(_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def verify_token(token: str) -> str | None:
    try:
        encoded, supplied_signature = str(token or "").split(".", 1)
        expected = hmac.new(
            _secret(), encoded.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(supplied_signature), expected):
            return None
        payload = json.loads(_decode(encoded))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return str(payload.get("u", "")).strip().lower() or None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def check_credentials(username: str, password: str) -> bool:
    load_env()
    normalized_user = str(username or "").strip().lower()
    raw_password = str(password or "")
    if not normalized_user or not raw_password:
        return False

    try:
        admin = get_admin_by_email(normalized_user)
    except Exception:
        admin = None
    if admin:
        stored = (
            admin.get("contrasena")
            or admin.get("password")
            or admin.get("contraseña")
            or admin.get("clave")
            or ""
        )
        if verify_password(stored, raw_password):
            return True

    configured_user = os.getenv("ADMIN_USERNAME", "").strip().lower()
    configured_password = os.getenv("ADMIN_PASSWORD", "")
    if configured_user and configured_password:
        return hmac.compare_digest(
            normalized_user, configured_user
        ) and hmac.compare_digest(raw_password, configured_password)

    # Compatibility with the emergency access used by the previous app.
    return hmac.compare_digest(normalized_user, "admin") and hmac.compare_digest(
        raw_password, "admin123"
    )


def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida.",
        )
    username = verify_token(authorization.split(" ", 1)[1])
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión venció. Inicia sesión nuevamente.",
        )
    return username


AdminUser = Annotated[str, Depends(require_admin)]
