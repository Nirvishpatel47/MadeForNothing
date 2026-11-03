"""
Editorial Posts & Articles Database Queries for MADE FOR NOTHING.
Handles published article fetching, landing selection, related reading, and administrative post management.
"""
import json
from datetime import datetime, timezone
from .connection import get_connection, _format_row


def get_landing_selected_posts(limit=4):
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


def get_filtered_posts_admin(post_type=None, is_published=None, show_on_landing=None, query=None, limit=50, offset=0):
    """Alias for get_all_posts_admin with query parameter naming."""
    return get_all_posts_admin(
        post_type=post_type,
        is_published=is_published,
        show_on_landing=show_on_landing,
        search=query,
        limit=limit,
        offset=offset
    )


def get_post_counts_admin():
    """Returns total, published, and draft post counts."""
    query = """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE is_published = TRUE) AS published,
            COUNT(*) FILTER (WHERE is_published = FALSE) AS drafts
        FROM posts
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            return dict(row) if row else {"total": 0, "published": 0, "drafts": 0}


def get_post_by_id(post_id):
    query = "SELECT * FROM posts WHERE id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_post_by_id_admin(post_id):
    return get_post_by_id(post_id)


def get_post_by_slug_admin(slug):
    query = "SELECT * FROM posts WHERE slug = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (slug,))
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
