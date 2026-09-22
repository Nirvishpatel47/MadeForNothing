import os
import json
import logging
from datetime import datetime, timezone
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("made_for_nothing.db")

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

# Content Types: writing, research, experiments, projects, books
VALID_TYPES = ["writing", "research", "experiments", "projects", "books"]


def get_pool():
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
    pool_instance = get_pool()
    if PSYCOPG_VERSION == 2:
        conn = pool_instance.getconn()
        try:
            yield conn
        finally:
            pool_instance.putconn(conn)
    elif PSYCOPG_VERSION == 3:
        with pool_instance.connection() as conn:
            yield conn


def init_db():
    """Initializes tables, columns, and indexes without using external .sql files."""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS posts (
        id SERIAL PRIMARY KEY,
        type VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL UNIQUE,
        excerpt TEXT NOT NULL,
        content_markdown TEXT NOT NULL,
        is_published BOOLEAN NOT NULL DEFAULT FALSE,
        show_on_landing BOOLEAN NOT NULL DEFAULT FALSE,
        published_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        tags TEXT[] DEFAULT '{}',
        external_links JSONB DEFAULT '[]'::jsonb,
        seo_title VARCHAR(255),
        seo_description TEXT,
        continue_reading_slugs TEXT[] DEFAULT '{}'
    );

    -- Schema evolution without external .sql files
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS show_on_landing BOOLEAN DEFAULT FALSE;

    CREATE INDEX IF NOT EXISTS idx_posts_type_published ON posts (type, is_published, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts (slug);
    CREATE INDEX IF NOT EXISTS idx_posts_published ON posts (is_published, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_landing ON posts (show_on_landing, is_published, published_at DESC);
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_query)
        conn.commit()
    logger.info("Database schema initialized successfully.")


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
    return item


# --- Public Queries ---

def get_landing_selected_posts(limit=6):
    """Returns published posts explicitly chosen for the landing page 'Start Here' section."""
    query = """
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links
        FROM posts
        WHERE is_published = TRUE AND show_on_landing = TRUE
        ORDER BY published_at DESC, created_at DESC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_recent_published_posts(limit=5, exclude_slugs=None):
    """Returns latest published items for recent activity list."""
    conditions = ["is_published = TRUE"]
    params = []
    if exclude_slugs:
        placeholders = ", ".join(["%s"] * len(exclude_slugs))
        conditions.append(f"slug NOT IN ({placeholders})")
        params.extend(exclude_slugs)

    query = f"""
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links
        FROM posts
        WHERE {" AND ".join(conditions)}
        ORDER BY published_at DESC, created_at DESC
        LIMIT %s
    """
    params.append(limit)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_published_posts(post_type=None, limit=50, offset=0):
    query = """
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links
        FROM posts
        WHERE is_published = TRUE
    """
    params = []
    if post_type:
        query += " AND type = %s"
        params.append(post_type)
    query += " ORDER BY published_at DESC, created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_published_post_by_slug(post_type, slug):
    query = """
        SELECT *
        FROM posts
        WHERE type = %s AND slug = %s AND is_published = TRUE
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_type, slug))
            row = cur.fetchone()
            return _format_row(row)


def get_continue_reading_posts(slugs):
    if not slugs:
        return []
    # Fetch maximum 3 posts
    valid_slugs = [s.strip() for s in slugs if s.strip()][:3]
    if not valid_slugs:
        return []

    placeholders = ", ".join(["%s"] * len(valid_slugs))
    query = f"""
        SELECT id, type, title, slug, excerpt, published_at, tags
        FROM posts
        WHERE slug IN ({placeholders}) AND is_published = TRUE
        LIMIT 3
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(valid_slugs))
            rows = cur.fetchall()
            items = [_format_row(r) for r in rows]
            # Order items to match the order in slugs
            slug_to_item = {item["slug"]: item for item in items}
            return [slug_to_item[s] for s in valid_slugs if s in slug_to_item]


def get_all_published_slugs():
    query = """
        SELECT type, slug, published_at, updated_at
        FROM posts
        WHERE is_published = TRUE
        ORDER BY published_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


# --- Admin Queries ---

def get_all_posts_admin(post_type=None, is_published=None, show_on_landing=None, search=None, limit=100, offset=0):
    conditions = ["1=1"]
    params = []

    if post_type:
        conditions.append("type = %s")
        params.append(post_type)
    if is_published is not None:
        conditions.append("is_published = %s")
        params.append(is_published)
    if show_on_landing is not None:
        conditions.append("show_on_landing = %s")
        params.append(show_on_landing)
    if search:
        conditions.append("(title ILIKE %s OR slug ILIKE %s OR excerpt ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])

    query = f"""
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, updated_at, tags
        FROM posts
        WHERE {" AND ".join(conditions)}
        ORDER BY updated_at DESC, created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_post_by_id(post_id):
    query = "SELECT * FROM posts WHERE id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_all_posts_for_selector(exclude_id=None):
    """Returns id, title, type, slug for selecting 'Continue Reading' posts."""
    query = "SELECT id, title, type, slug FROM posts WHERE is_published = TRUE"
    params = []
    if exclude_id:
        query += " AND id != %s"
        params.append(exclude_id)
    query += " ORDER BY published_at DESC LIMIT 100"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def create_post(data):
    now = datetime.now(timezone.utc)
    is_published = bool(data.get("is_published", False))
    show_on_landing = bool(data.get("show_on_landing", False))
    published_at = now if is_published else None

    # external_links as json string
    external_links = data.get("external_links", [])
    if isinstance(external_links, (list, dict)):
        external_links_json = json.dumps(external_links)
    else:
        external_links_json = "[]"

    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    continue_reading_slugs = data.get("continue_reading_slugs", [])
    if isinstance(continue_reading_slugs, str):
        continue_reading_slugs = [s.strip() for s in continue_reading_slugs.split(",") if s.strip()]
    continue_reading_slugs = continue_reading_slugs[:3]

    query = """
        INSERT INTO posts (
            type, title, slug, excerpt, content_markdown,
            is_published, show_on_landing, published_at, created_at, updated_at,
            tags, external_links, seo_title, seo_description, continue_reading_slugs
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, slug, type
    """
    params = (
        data["type"],
        data["title"],
        data["slug"],
        data["excerpt"],
        data["content_markdown"],
        is_published,
        show_on_landing,
        published_at,
        now,
        now,
        tags,
        external_links_json,
        data.get("seo_title") or None,
        data.get("seo_description") or None,
        continue_reading_slugs
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            created = cur.fetchone()
        conn.commit()
        return dict(created)


def update_post(post_id, data):
    now = datetime.now(timezone.utc)
    current = get_post_by_id(post_id)
    if not current:
        return None

    is_published = bool(data.get("is_published", False))
    show_on_landing = bool(data.get("show_on_landing", False))
    published_at = current.get("published_at")
    if is_published and not published_at:
        published_at = now

    external_links = data.get("external_links", [])
    if isinstance(external_links, (list, dict)):
        external_links_json = json.dumps(external_links)
    else:
        external_links_json = "[]"

    tags = data.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    continue_reading_slugs = data.get("continue_reading_slugs", [])
    if isinstance(continue_reading_slugs, str):
        continue_reading_slugs = [s.strip() for s in continue_reading_slugs.split(",") if s.strip()]
    continue_reading_slugs = continue_reading_slugs[:3]

    query = """
        UPDATE posts
        SET type = %s,
            title = %s,
            slug = %s,
            excerpt = %s,
            content_markdown = %s,
            is_published = %s,
            show_on_landing = %s,
            published_at = %s,
            updated_at = %s,
            tags = %s,
            external_links = %s,
            seo_title = %s,
            seo_description = %s,
            continue_reading_slugs = %s
        WHERE id = %s
        RETURNING id, slug, type
    """
    params = (
        data["type"],
        data["title"],
        data["slug"],
        data["excerpt"],
        data["content_markdown"],
        is_published,
        show_on_landing,
        published_at,
        now,
        tags,
        external_links_json,
        data.get("seo_title") or None,
        data.get("seo_description") or None,
        continue_reading_slugs,
        post_id
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            updated = cur.fetchone()
        conn.commit()
        return dict(updated)


def delete_post(post_id):
    query = "DELETE FROM posts WHERE id = %s RETURNING id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_id,))
            deleted = cur.fetchone()
        conn.commit()
        return bool(deleted)


def toggle_publish_status(post_id):
    post = get_post_by_id(post_id)
    if not post:
        return None

    new_status = not post["is_published"]
    now = datetime.now(timezone.utc)
    published_at = post["published_at"]
    if new_status and not published_at:
        published_at = now

    query = """
        UPDATE posts
        SET is_published = %s,
            published_at = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING id, is_published
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (new_status, published_at, now, post_id))
            updated = cur.fetchone()
        conn.commit()
        return dict(updated)


def toggle_landing_status(post_id):
    post = get_post_by_id(post_id)
    if not post:
        return None

    new_status = not post.get("show_on_landing", False)
    now = datetime.now(timezone.utc)

    query = """
        UPDATE posts
        SET show_on_landing = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING id, show_on_landing
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (new_status, now, post_id))
            updated = cur.fetchone()
        conn.commit()
        return dict(updated)
