"""
Database Connection & Pool Management for MADE FOR NOTHING.
Supports both psycopg2 and psycopg v3 drivers with thread-safe connection pooling
and uniform dictionary row formatting.
"""
import os
import json
import logging
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("made_for_nothing.database")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Support psycopg2 or psycopg (v3)
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG_VERSION = 2
except ImportError:
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        PSYCOPG_VERSION = 3
    except ImportError:
        PSYCOPG_VERSION = None

_pool = None

# Supported publication content types
VALID_TYPES = ["writing", "research", "experiments", "projects", "books"]


def get_pool():
    """Returns the shared connection pool, initializing it if not already present."""
    global _pool
    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not configured.")

    # Standardize connection string for postgresql
    dsn = DATABASE_URL
    if dsn.startswith("postgres://"):
        dsn = dsn.replace("postgres://", "postgresql://", 1)

    if PSYCOPG_VERSION == 2:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn,
            cursor_factory=RealDictCursor
        )
    elif PSYCOPG_VERSION == 3:
        _pool = ConnectionPool(conninfo=dsn, min_size=1, max_size=10, kwargs={"row_factory": dict_row})
    else:
        raise RuntimeError("No compatible PostgreSQL driver found. Please install psycopg2-binary or psycopg[binary].")

    return _pool


@contextmanager
def get_connection():
    """Context manager yielding a pooled PostgreSQL connection with automatic rollback on failure."""
    pool_instance = get_pool()
    if PSYCOPG_VERSION == 2:
        conn = pool_instance.getconn()
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            pool_instance.putconn(conn)
    elif PSYCOPG_VERSION == 3:
        with pool_instance.connection() as conn:
            try:
                yield conn
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise


def _format_row(row):
    """Normalize row types across psycopg2 and psycopg3."""
    if not row:
        return None
    item = dict(row)

    # Ensure tags is a list
    if item.get("tags") is None:
        item["tags"] = []

    # Ensure continue_reading_slugs is a list
    if item.get("continue_reading_slugs") is None:
        item["continue_reading_slugs"] = []

    # Ensure show_on_landing is a boolean
    if "show_on_landing" in item:
        item["show_on_landing"] = bool(item.get("show_on_landing", False))

    # Ensure external_links is a list of dicts
    links = item.get("external_links")
    if isinstance(links, str):
        try:
            item["external_links"] = json.loads(links)
        except json.JSONDecodeError:
            item["external_links"] = []
    elif links is None:
        item["external_links"] = []

    # Ensure faq is a list of dicts
    faq_data = item.get("faq")
    if isinstance(faq_data, str):
        try:
            item["faq"] = json.loads(faq_data)
        except json.JSONDecodeError:
            item["faq"] = []
    elif faq_data is None:
        item["faq"] = []

    return item
