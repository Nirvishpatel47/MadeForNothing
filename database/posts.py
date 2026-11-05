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
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links,
               featured_image_url, featured_image_alt, featured_image_width, featured_image_height
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
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links,
               featured_image_url, featured_image_alt, featured_image_width, featured_image_height
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
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, tags, external_links,
               featured_image_url, featured_image_alt, featured_image_width, featured_image_height
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
        SELECT id, type, title, slug, excerpt, content_markdown, is_published, show_on_landing, published_at, created_at, updated_at, tags,
               featured_image_url, featured_image_alt, featured_image_width, featured_image_height
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

    featured_image_url = data.get("featured_image_url") or None
    featured_image_key = data.get("featured_image_key") or None
    featured_image_alt = data.get("featured_image_alt") or None
    featured_image_width = data.get("featured_image_width") or None
    featured_image_height = data.get("featured_image_height") or None
    featured_image_size = data.get("featured_image_size") or None
    featured_image_mime = data.get("featured_image_mime") or None
    featured_image_filename = data.get("featured_image_filename") or None

    query = """
        INSERT INTO posts (
            type, title, slug, excerpt, content_markdown,
            is_published, show_on_landing, published_at, created_at, updated_at,
            tags, external_links, seo_title, seo_description, continue_reading_slugs,
            featured_image_url, featured_image_key, featured_image_alt,
            featured_image_width, featured_image_height, featured_image_size,
            featured_image_mime, featured_image_filename
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        continue_reading_slugs,
        featured_image_url,
        featured_image_key,
        featured_image_alt,
        featured_image_width,
        featured_image_height,
        featured_image_size,
        featured_image_mime,
        featured_image_filename
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

    # Handle image updates or explicit removal
    if data.get("remove_featured_image"):
        featured_image_url = None
        featured_image_key = None
        featured_image_alt = None
        featured_image_width = None
        featured_image_height = None
        featured_image_size = None
        featured_image_mime = None
        featured_image_filename = None
    elif "featured_image_url" in data or "featured_image_key" in data:
        featured_image_url = data.get("featured_image_url") or None
        featured_image_key = data.get("featured_image_key") or None
        featured_image_alt = data.get("featured_image_alt") or None
        featured_image_width = data.get("featured_image_width") or None
        featured_image_height = data.get("featured_image_height") or None
        featured_image_size = data.get("featured_image_size") or None
        featured_image_mime = data.get("featured_image_mime") or None
        featured_image_filename = data.get("featured_image_filename") or None
    else:
        # Preserve existing image fields if not modified
        featured_image_url = current.get("featured_image_url")
        featured_image_key = current.get("featured_image_key")
        featured_image_alt = data.get("featured_image_alt", current.get("featured_image_alt"))
        featured_image_width = current.get("featured_image_width")
        featured_image_height = current.get("featured_image_height")
        featured_image_size = current.get("featured_image_size")
        featured_image_mime = current.get("featured_image_mime")
        featured_image_filename = current.get("featured_image_filename")

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
            continue_reading_slugs = %s,
            featured_image_url = %s,
            featured_image_key = %s,
            featured_image_alt = %s,
            featured_image_width = %s,
            featured_image_height = %s,
            featured_image_size = %s,
            featured_image_mime = %s,
            featured_image_filename = %s
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
        featured_image_url,
        featured_image_key,
        featured_image_alt,
        featured_image_width,
        featured_image_height,
        featured_image_size,
        featured_image_mime,
        featured_image_filename,
        post_id
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            updated = cur.fetchone()
        conn.commit()
        return dict(updated)


def delete_post(post_id):
    # If the post has an R2 image, clean it up
    try:
        current = get_post_by_id(post_id)
        if current and current.get("featured_image_key"):
            from r2_storage import delete_image_from_r2
            delete_image_from_r2(current["featured_image_key"])
    except Exception as e:
        import logging
        logging.getLogger("made_for_nothing.database.posts").warning(
            f"Could not clean up R2 image for deleted post {post_id}: {e}"
        )

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
