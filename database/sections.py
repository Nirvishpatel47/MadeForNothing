"""
Sections & Content Discovery Database Operations for MADE FOR NOTHING.
=====================================================================
Provides full CRUD, sorting, category assignment, and post/course associations
for the section-based content discovery architecture.
"""
import re
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .connection import get_connection, _format_row

logger = logging.getLogger("made_for_nothing.database.sections")

VALID_SECTION_TYPES = ["writing", "research", "experiments", "projects", "books", "courses"]


def slugify(text: str) -> str:
    """Generates a clean, URL-safe slug from text."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text or "section"


# ==============================================================================
# Section CRUD Operations
# ==============================================================================

def get_all_sections_admin() -> List[Dict[str, Any]]:
    """
    Returns all sections for the admin portal, ordered by sort_order and name,
    including the count of associated posts and courses.
    """
    query = """
        SELECT s.*,
               COUNT(DISTINCT ps.post_id) AS post_count,
               COUNT(DISTINCT cs.course_id) AS course_count
        FROM sections s
        LEFT JOIN post_sections ps ON ps.section_id = s.id
        LEFT JOIN course_sections cs ON cs.section_id = s.id
        GROUP BY s.id
        ORDER BY s.sort_order ASC, s.name ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_section_by_id(section_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single section by primary key ID."""
    query = "SELECT * FROM sections WHERE id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (section_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_section_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Fetches a single section by unique URL slug."""
    query = "SELECT * FROM sections WHERE slug = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (slug.strip().lower(),))
            row = cur.fetchone()
            return _format_row(row)


def create_section(data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new content discovery section."""
    name = data.get("name", "").strip()
    if not name:
        raise ValueError("Section name is required.")

    raw_slug = data.get("slug", "").strip()
    slug = slugify(raw_slug) if raw_slug else slugify(name)

    description = data.get("description", "").strip()
    content_types = data.get("content_types", [])
    if isinstance(content_types, str):
        content_types = [t.strip().lower() for t in content_types.split(",") if t.strip()]

    # Normalize content types
    clean_types = [t for t in content_types if t in VALID_SECTION_TYPES or t == "all"]

    is_featured = bool(data.get("is_featured", False))
    is_published = bool(data.get("is_published", True))
    sort_order = int(data.get("sort_order", 0))

    query = """
        INSERT INTO sections (
            name, slug, description, content_types,
            is_featured, is_published, sort_order,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                name, slug, description, clean_types,
                is_featured, is_published, sort_order
            ))
            created = cur.fetchone()
        conn.commit()
        return dict(created)


def update_section(section_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates an existing section."""
    current = get_section_by_id(section_id)
    if not current:
        return None

    name = data.get("name", current["name"]).strip()
    if not name:
        raise ValueError("Section name cannot be empty.")

    raw_slug = data.get("slug", current["slug"]).strip()
    slug = slugify(raw_slug) if raw_slug else slugify(name)

    description = data.get("description", current.get("description", "")).strip()

    if "content_types" in data:
        content_types = data.get("content_types", [])
        if isinstance(content_types, str):
            content_types = [t.strip().lower() for t in content_types.split(",") if t.strip()]
        clean_types = [t for t in content_types if t in VALID_SECTION_TYPES or t == "all"]
    else:
        clean_types = current.get("content_types", [])

    is_featured = bool(data.get("is_featured", current.get("is_featured", False)))
    is_published = bool(data.get("is_published", current.get("is_published", True)))
    sort_order = int(data.get("sort_order", current.get("sort_order", 0)))

    query = """
        UPDATE sections
        SET name = %s,
            slug = %s,
            description = %s,
            content_types = %s,
            is_featured = %s,
            is_published = %s,
            sort_order = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (
                name, slug, description, clean_types,
                is_featured, is_published, sort_order, section_id
            ))
            updated = cur.fetchone()
        conn.commit()
        return dict(updated) if updated else None


def delete_section(section_id: int) -> bool:
    """Deletes a section and cascades associations."""
    query = "DELETE FROM sections WHERE id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (section_id,))
        conn.commit()
        return True


def toggle_section_publish(section_id: int) -> Optional[bool]:
    """Toggles the published status of a section."""
    query = """
        UPDATE sections
        SET is_published = NOT is_published,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING is_published
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (section_id,))
            row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


def reorder_sections(orders: Dict[int, int]) -> bool:
    """Batch updates sort_order for a mapping of {section_id: order}."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            for s_id, order in orders.items():
                cur.execute(
                    "UPDATE sections SET sort_order = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (int(order), int(s_id))
                )
        conn.commit()
        return True


# ==============================================================================
# Public Discovery & Filtering Operations
# ==============================================================================

def get_sections_for_type(content_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns all published sections matching the specified content_type (or all types if None).
    Includes the count of published articles matching that section and content_type.
    """
    params = []
    where_type = ""
    if content_type:
        where_type = "AND (content_types = '{}' OR 'all' = ANY(content_types) OR %s = ANY(content_types))"
        params.append(content_type)

    query = f"""
        SELECT s.*,
               COUNT(DISTINCT p.id) AS post_count
        FROM sections s
        LEFT JOIN post_sections ps ON ps.section_id = s.id
        LEFT JOIN posts p ON p.id = ps.post_id AND p.is_published = TRUE
        WHERE s.is_published = TRUE {where_type}
        GROUP BY s.id
        ORDER BY s.sort_order ASC, s.name ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_featured_sections_for_type(content_type: str, limit: int = 4) -> List[Dict[str, Any]]:
    """
    Retrieves the 3-4 top featured sections to display in the category pill bar.
    Falls back to first published sections if none are explicitly marked as is_featured.
    """
    query = """
        SELECT s.*,
               COUNT(DISTINCT p.id) AS post_count
        FROM sections s
        LEFT JOIN post_sections ps ON ps.section_id = s.id
        LEFT JOIN posts p ON p.id = ps.post_id AND p.is_published = TRUE
        WHERE s.is_published = TRUE
          AND (content_types = '{}' OR 'all' = ANY(content_types) OR %s = ANY(content_types))
        GROUP BY s.id
        ORDER BY s.is_featured DESC, s.sort_order ASC, s.name ASC
        LIMIT %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (content_type, limit))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


# ==============================================================================
# Post / Article Section Association Operations
# ==============================================================================

def get_sections_for_post(post_id: int) -> List[Dict[str, Any]]:
    """Returns the list of sections assigned to a post."""
    query = """
        SELECT s.id, s.name, s.slug, s.description, s.is_featured
        FROM sections s
        JOIN post_sections ps ON ps.section_id = s.id
        WHERE ps.post_id = %s AND s.is_published = TRUE
        ORDER BY s.sort_order ASC, s.name ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_section_ids_for_post(post_id: int) -> List[int]:
    """Returns the list of section IDs assigned to a post."""
    query = "SELECT section_id FROM post_sections WHERE post_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (post_id,))
            rows = cur.fetchall()
            return [r["section_id"] if isinstance(r, dict) else r[0] for r in rows]


def set_post_sections(post_id: int, section_ids: List[int]) -> bool:
    """
    Synchronizes the assigned sections for a post.
    Replaces existing relationships with the given list of section IDs.
    """
    clean_ids = [int(sid) for sid in section_ids if str(sid).isdigit()]
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Clear old associations
            cur.execute("DELETE FROM post_sections WHERE post_id = %s", (post_id,))
            # Insert new associations
            for sid in clean_ids:
                cur.execute(
                    "INSERT INTO post_sections (post_id, section_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (post_id, sid)
                )
        conn.commit()
        return True


# ==============================================================================
# Course Section Association Operations
# ==============================================================================

def get_sections_for_course(course_id: int) -> List[Dict[str, Any]]:
    """Returns the list of sections assigned to a course."""
    query = """
        SELECT s.id, s.name, s.slug, s.description, s.is_featured
        FROM sections s
        JOIN course_sections cs ON cs.section_id = s.id
        WHERE cs.course_id = %s AND s.is_published = TRUE
        ORDER BY s.sort_order ASC, s.name ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_section_ids_for_course(course_id: int) -> List[int]:
    """Returns the list of section IDs assigned to a course."""
    query = "SELECT section_id FROM course_sections WHERE course_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            rows = cur.fetchall()
            return [r["section_id"] if isinstance(r, dict) else r[0] for r in rows]


def set_course_sections(course_id: int, section_ids: List[int]) -> bool:
    """Synchronizes the assigned sections for a course."""
    clean_ids = [int(sid) for sid in section_ids if str(sid).isdigit()]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM course_sections WHERE course_id = %s", (course_id,))
            for sid in clean_ids:
                cur.execute(
                    "INSERT INTO course_sections (course_id, section_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (course_id, sid)
                )
        conn.commit()
        return True


# ==============================================================================
# Seed Initial Sections If Empty
# ==============================================================================

def seed_default_sections_if_empty():
    """
    Seeds initial default sections matching the research & editorial archive
    if the sections table has 0 rows. Links existing posts to relevant sections.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sections")
            res = cur.fetchone()
            count = res[0] if res else 0
            if count > 0:
                return

            logger.info("Seeding initial default content discovery sections...")
            defaults = [
                {
                    "name": "Cognitive Philosophy",
                    "slug": "cognitive-philosophy",
                    "description": "Studies on mental models, perception, behavioral psychology, and clarity.",
                    "content_types": ["writing", "research"],
                    "is_featured": True,
                    "sort_order": 1,
                },
                {
                    "name": "Distributed Systems",
                    "slug": "distributed-systems",
                    "description": "Consensus protocols, durable state machines, fault tolerance, and architectures.",
                    "content_types": ["research", "projects", "courses"],
                    "is_featured": True,
                    "sort_order": 2,
                },
                {
                    "name": "Habits & Consistency",
                    "slug": "habits-consistency",
                    "description": "Explorations into physical discipline, daily systems, motivation, and endurance.",
                    "content_types": ["writing", "research"],
                    "is_featured": True,
                    "sort_order": 3,
                },
                {
                    "name": "Experimental Software",
                    "slug": "experimental-software",
                    "description": "Live software experiments, product validation, minimal apps, and post-mortems.",
                    "content_types": ["experiments", "projects"],
                    "is_featured": True,
                    "sort_order": 4,
                },
                {
                    "name": "Fundamental Sciences",
                    "slug": "fundamental-sciences",
                    "description": "Foundational chemistry, physics, computing theory, and first-principles learning.",
                    "content_types": ["writing", "books", "courses"],
                    "is_featured": True,
                    "sort_order": 5,
                },
            ]

            created_map = {}
            for d in defaults:
                cur.execute("""
                    INSERT INTO sections (name, slug, description, content_types, is_featured, is_published, sort_order)
                    VALUES (%s, %s, %s, %s, %s, TRUE, %s)
                    RETURNING id, slug
                """, (d["name"], d["slug"], d["description"], d["content_types"], d["is_featured"], d["sort_order"]))
                row = cur.fetchone()
                created_map[row[1] if isinstance(row, tuple) else row["slug"]] = row[0] if isinstance(row, tuple) else row["id"]

            # Automatically map existing posts to appropriate sections
            cur.execute("SELECT id, type, title, tags FROM posts")
            posts = cur.fetchall()
            for p in posts:
                pid = p[0] if isinstance(p, tuple) else p["id"]
                ptype = p[1] if isinstance(p, tuple) else p["type"]
                ptitle = (p[2] if isinstance(p, tuple) else p["title"]).lower()
                ptags = [t.lower() for t in (p[3] if isinstance(p, tuple) else p.get("tags") or [])]

                target_sids = []
                if "exercise" in ptitle or "dopamine" in ptitle or "habits" in ptitle:
                    target_sids.append(created_map.get("habits-consistency"))
                if "overthinking" in ptitle or "believe" in ptitle or "motivation" in ptitle:
                    target_sids.append(created_map.get("cognitive-philosophy"))
                if "social media" in ptitle or "research" in ptype:
                    target_sids.append(created_map.get("cognitive-philosophy"))
                if "inventory" in ptitle or "experiment" in ptype or "problem" in ptitle:
                    target_sids.append(created_map.get("experimental-software"))
                if "chemistry" in ptitle or "atoms" in ptitle:
                    target_sids.append(created_map.get("fundamental-sciences"))

                for sid in filter(None, set(target_sids)):
                    cur.execute(
                        "INSERT INTO post_sections (post_id, section_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (pid, sid)
                    )

        conn.commit()
        logger.info("Successfully seeded default sections and mapped initial posts.")
