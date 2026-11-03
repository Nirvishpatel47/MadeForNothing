"""
Courses, Lessons & Curriculum Q&A Database Operations for MADE FOR NOTHING.
Handles published course retrieval, lesson video management, reordering, and question CRUD.
"""
import json
from datetime import datetime, timezone
from .connection import get_connection, _format_row


def get_published_courses():
    """Returns all published courses along with lesson count and estimated total duration."""
    query = """
        SELECT c.*,
               COUNT(cl.id) FILTER (WHERE cl.is_published = TRUE) AS lesson_count,
               COALESCE(SUM(cl.duration_seconds) FILTER (WHERE cl.is_published = TRUE), 0) AS total_duration_seconds
        FROM courses c
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        WHERE c.is_published = TRUE
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_published_course_by_slug(slug: str):
    query = """
        SELECT c.*,
               COUNT(cl.id) FILTER (WHERE cl.is_published = TRUE) AS lesson_count,
               COALESCE(SUM(cl.duration_seconds) FILTER (WHERE cl.is_published = TRUE), 0) AS total_duration_seconds
        FROM courses c
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        WHERE c.slug = %s AND c.is_published = TRUE
        GROUP BY c.id
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (slug,))
            row = cur.fetchone()
            return _format_row(row)


def get_course_by_id(course_id: int):
    query = """
        SELECT c.*,
               COUNT(cl.id) AS total_lessons,
               COALESCE(SUM(cl.duration_seconds), 0) AS total_duration_seconds
        FROM courses c
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        WHERE c.id = %s
        GROUP BY c.id
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_course_by_slug_admin(slug: str):
    query = """
        SELECT c.*,
               COUNT(cl.id) AS lesson_count,
               COALESCE(SUM(cl.duration_seconds), 0) AS total_duration_seconds
        FROM courses c
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        WHERE c.slug = %s
        GROUP BY c.id
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (slug,))
            row = cur.fetchone()
            return _format_row(row)


def get_all_courses_admin():
    query = """
        SELECT c.*,
               COUNT(DISTINCT cl.id) AS lesson_count,
               COUNT(DISTINCT ce.id) FILTER (WHERE ce.status = 'active') AS student_count
        FROM courses c
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        LEFT JOIN course_enrollments ce ON c.id = ce.course_id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def create_course(data: dict):
    now = datetime.now(timezone.utc)
    faq_json = json.dumps(data.get("faq", [])) if isinstance(data.get("faq"), list) else "[]"
    query = """
        INSERT INTO courses (
            title, slug, subtitle, description, what_you_will_learn,
            target_audience, price, thumbnail, is_published, faq,
            instructor_bio, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, slug, title
    """
    params = (
        data["title"].strip(),
        data["slug"].strip(),
        data.get("subtitle", "").strip(),
        data.get("description", "").strip(),
        data.get("what_you_will_learn", "").strip(),
        data.get("target_audience", "").strip(),
        int(data.get("price", 0)),
        data.get("thumbnail", "").strip(),
        bool(data.get("is_published", False)),
        faq_json,
        data.get("instructor_bio", "").strip(),
        now,
        now
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            created = cur.fetchone()
        conn.commit()
        return dict(created)


def update_course(course_id: int, data: dict):
    now = datetime.now(timezone.utc)
    faq_json = json.dumps(data.get("faq", [])) if isinstance(data.get("faq"), list) else "[]"
    query = """
        UPDATE courses
        SET title = %s,
            slug = %s,
            subtitle = %s,
            description = %s,
            what_you_will_learn = %s,
            target_audience = %s,
            price = %s,
            thumbnail = %s,
            is_published = %s,
            faq = %s,
            instructor_bio = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING id, slug, title
    """
    params = (
        data["title"].strip(),
        data["slug"].strip(),
        data.get("subtitle", "").strip(),
        data.get("description", "").strip(),
        data.get("what_you_will_learn", "").strip(),
        data.get("target_audience", "").strip(),
        int(data.get("price", 0)),
        data.get("thumbnail", "").strip(),
        bool(data.get("is_published", False)),
        faq_json,
        data.get("instructor_bio", "").strip(),
        now,
        course_id
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            updated = cur.fetchone()
        conn.commit()
        return dict(updated) if updated else None


def delete_course(course_id: int):
    query = "DELETE FROM courses WHERE id = %s RETURNING id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            deleted = cur.fetchone()
        conn.commit()
        return bool(deleted)


def toggle_course_publish_status(course_id: int):
    query = """
        UPDATE courses
        SET is_published = NOT is_published,
            updated_at = %s
        WHERE id = %s
        RETURNING id, is_published
    """
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (now, course_id))
            updated = cur.fetchone()
        conn.commit()
        return dict(updated) if updated else None


# --- Lesson Queries ---

def get_published_lessons_by_course(course_id: int):
    query = """
        SELECT id, course_id, title, slug, order_index, description,
               duration_seconds, is_published, mux_status, created_at
        FROM course_lessons
        WHERE course_id = %s AND is_published = TRUE
        ORDER BY order_index ASC, id ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_all_lessons_admin(course_id: int):
    query = """
        SELECT cl.*,
               (SELECT COUNT(*) FROM course_questions cq WHERE cq.lesson_id = cl.id) AS question_count
        FROM course_lessons cl
        WHERE cl.course_id = %s
        ORDER BY cl.order_index ASC, cl.id ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_lesson_by_id(lesson_id: int):
    query = """
        SELECT cl.*, c.title AS course_title, c.slug AS course_slug, c.is_published AS course_is_published
        FROM course_lessons cl
        JOIN courses c ON cl.course_id = c.id
        WHERE cl.id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lesson_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_lesson_by_course_and_slug(course_id: int, slug: str):
    query = """
        SELECT cl.*, c.title AS course_title, c.slug AS course_slug
        FROM course_lessons cl
        JOIN courses c ON cl.course_id = c.id
        WHERE cl.course_id = %s AND cl.slug = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (course_id, slug))
            row = cur.fetchone()
            return _format_row(row)


def create_lesson(data: dict):
    now = datetime.now(timezone.utc)
    query = """
        INSERT INTO course_lessons (
            course_id, title, slug, order_index, description, content_markdown,
            mux_asset_id, mux_playback_id, mux_upload_id, mux_status,
            duration_seconds, is_published, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, course_id, slug, title
    """
    params = (
        data["course_id"],
        data["title"].strip(),
        data["slug"].strip(),
        int(data.get("order_index", 0)),
        data.get("description", "").strip(),
        data.get("content_markdown", ""),
        data.get("mux_asset_id", "").strip(),
        data.get("mux_playback_id", "").strip(),
        data.get("mux_upload_id", "").strip(),
        data.get("mux_status", "none").strip(),
        int(data.get("duration_seconds", 0)),
        bool(data.get("is_published", True)),
        now,
        now
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            created = cur.fetchone()
        conn.commit()
        return dict(created)


def update_lesson(lesson_id: int, data: dict):
    now = datetime.now(timezone.utc)
    query = """
        UPDATE course_lessons
        SET title = %s,
            slug = %s,
            order_index = %s,
            description = %s,
            content_markdown = %s,
            mux_asset_id = %s,
            mux_playback_id = %s,
            mux_upload_id = %s,
            mux_status = %s,
            duration_seconds = %s,
            is_published = %s,
            updated_at = %s
        WHERE id = %s
        RETURNING id, course_id, slug, title
    """
    params = (
        data["title"].strip(),
        data["slug"].strip(),
        int(data.get("order_index", 0)),
        data.get("description", "").strip(),
        data.get("content_markdown", ""),
        data.get("mux_asset_id", "").strip(),
        data.get("mux_playback_id", "").strip(),
        data.get("mux_upload_id", "").strip(),
        data.get("mux_status", "none").strip(),
        int(data.get("duration_seconds", 0)),
        bool(data.get("is_published", True)),
        now,
        lesson_id
    )
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            updated = cur.fetchone()
        conn.commit()
        return dict(updated) if updated else None


def update_lesson_mux(
    lesson_id: int,
    mux_asset_id: str = None,
    mux_playback_id: str = None,
    mux_upload_id: str = None,
    mux_status: str = None,
    duration_seconds: int = None
):
    updates = ["updated_at = %s"]
    now = datetime.now(timezone.utc)
    params = [now]

    if mux_asset_id is not None:
        updates.append("mux_asset_id = %s")
        params.append(mux_asset_id)
    if mux_playback_id is not None:
        updates.append("mux_playback_id = %s")
        params.append(mux_playback_id)
    if mux_upload_id is not None:
        updates.append("mux_upload_id = %s")
        params.append(mux_upload_id)
    if mux_status is not None:
        updates.append("mux_status = %s")
        params.append(mux_status)
    if duration_seconds is not None:
        updates.append("duration_seconds = %s")
        params.append(int(duration_seconds))

    params.append(lesson_id)
    query = f"UPDATE course_lessons SET {', '.join(updates)} WHERE id = %s RETURNING id, mux_status, mux_playback_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            updated = cur.fetchone()
        conn.commit()
        return dict(updated) if updated else None


def delete_lesson(lesson_id: int):
    query = "DELETE FROM course_lessons WHERE id = %s RETURNING id, course_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lesson_id,))
            deleted = cur.fetchone()
        conn.commit()
        return dict(deleted) if deleted else None


def reorder_lessons(course_id: int, ordered_ids: list):
    query = "UPDATE course_lessons SET order_index = %s WHERE id = %s AND course_id = %s"
    with get_connection() as conn:
        with conn.cursor() as cur:
            for idx, lesson_id in enumerate(ordered_ids):
                cur.execute(query, (idx + 1, int(lesson_id), course_id))
        conn.commit()
    return True


# --- Questions & Answers Queries ---

def get_questions_by_lesson(lesson_id: int):
    query = """
        SELECT id, lesson_id, question, answer, sort_order, created_at, updated_at
        FROM course_questions
        WHERE lesson_id = %s
        ORDER BY sort_order ASC, id ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lesson_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def create_question(lesson_id: int, question: str, answer: str, sort_order: int = 0):
    now = datetime.now(timezone.utc)
    query = """
        INSERT INTO course_questions (lesson_id, question, answer, sort_order, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, lesson_id, question, answer, sort_order
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lesson_id, question.strip(), answer.strip(), sort_order, now, now))
            row = cur.fetchone()
        conn.commit()
        return dict(row)


def update_question(question_id: int, question: str, answer: str, sort_order: int = None):
    now = datetime.now(timezone.utc)
    if sort_order is not None:
        query = """
            UPDATE course_questions
            SET question = %s, answer = %s, sort_order = %s, updated_at = %s
            WHERE id = %s
            RETURNING id, lesson_id, question, answer, sort_order
        """
        params = (question.strip(), answer.strip(), int(sort_order), now, question_id)
    else:
        query = """
            UPDATE course_questions
            SET question = %s, answer = %s, updated_at = %s
            WHERE id = %s
            RETURNING id, lesson_id, question, answer, sort_order
        """
        params = (question.strip(), answer.strip(), now, question_id)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def delete_question(question_id: int):
    query = "DELETE FROM course_questions WHERE id = %s RETURNING id, lesson_id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (question_id,))
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def get_question_by_id(question_id: int):
    query = "SELECT * FROM course_questions WHERE id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (question_id,))
            row = cur.fetchone()
            return _format_row(row)
