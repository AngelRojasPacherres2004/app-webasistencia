from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
from threading import Lock

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
except Exception:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None
    ThreadedConnectionPool = None


ENV_PATHS = (Path(".env"), Path(".env.local"))
_CONNECTION_POOL = None
_POOL_LOCK = Lock()


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


def _get_connection_pool():
    global _CONNECTION_POOL
    if _CONNECTION_POOL is not None:
        return _CONNECTION_POOL

    with _POOL_LOCK:
        if _CONNECTION_POOL is not None:
            return _CONNECTION_POOL

        load_env()
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            raise RuntimeError("Falta `DATABASE_URL` en `.env`.")
        if ThreadedConnectionPool is None:
            raise RuntimeError("Falta instalar `psycopg2-binary`.")

        _CONNECTION_POOL = ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=database_url,
            sslmode="require",
            cursor_factory=RealDictCursor,
        )
        return _CONNECTION_POOL


@contextmanager
def get_pooled_connection():
    """Reuse PostgreSQL connections and always return them in a clean state."""
    pool = _get_connection_pool()
    connection = pool.getconn()
    discard_connection = False
    try:
        yield connection
    except Exception:
        discard_connection = True
        if not connection.closed:
            try:
                connection.rollback()
            except Exception:
                pass
        raise
    finally:
        if not connection.closed and not discard_connection:
            try:
                connection.rollback()
            except Exception:
                discard_connection = True
        pool.putconn(
            connection,
            close=discard_connection or bool(connection.closed),
        )
