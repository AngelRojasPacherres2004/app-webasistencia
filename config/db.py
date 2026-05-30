from __future__ import annotations

import os
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None


ENV_PATHS = (Path(".env"), Path(".env.local"))


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_env():
    for path in ENV_PATHS:
        _load_env_file(path)


def get_connection():
    load_env()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("Falta `DATABASE_URL` en `.env`.")
    if psycopg2 is None:
        raise RuntimeError("Falta instalar `psycopg2-binary`.")
    return psycopg2.connect(
        database_url,
        sslmode="require",
        cursor_factory=RealDictCursor,
    )
