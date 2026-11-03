"""
Student Course Enrollments Database Operations for MADE FOR NOTHING.
Handles active enrollment verification, progress calculation, and administrative access granting.
"""
from datetime import datetime, timezone
from .connection import get_connection, _format_row
from .schema import repair_enrolled_users_foreign_keys


def get_enrollment(user_id: int, course_id: int):
    """Fetches single enrollment record by user and course."""
    query = "SELECT * FROM course_enrollments WHERE user_id = %s AND course_id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, course_id))
            row = cur.fetchone()
            return _format_row(row)


def is_user_enrolled(user_id: int, course_id: int) -> bool:
    """Returns True if the student has an active enrollment in the specified course."""
    if not user_id or not course_id:
        return False
    query = "SELECT status FROM course_enrollments WHERE user_id = %s AND course_id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, course_id))
            row = cur.fetchone()
            return bool(row and row["status"] == "active")


def get_user_enrolled_courses(user_id: int):
    """Retrieves all courses actively enrolled by a user with calculated progress."""
    query = """
        SELECT c.*,
               ce.status AS enrollment_status,
               ce.granted_at,
               COUNT(DISTINCT cl.id) FILTER (WHERE cl.is_published = TRUE) AS total_lessons,
               COUNT(DISTINCT lp.id) FILTER (WHERE lp.completed = TRUE) AS completed_lessons
        FROM course_enrollments ce
        JOIN courses c ON ce.course_id = c.id
        LEFT JOIN course_lessons cl ON c.id = cl.course_id
        LEFT JOIN lesson_progress lp ON lp.lesson_id = cl.id AND lp.user_id = ce.user_id
        WHERE ce.user_id = %s AND ce.status = 'active'
        GROUP BY c.id, ce.status, ce.granted_at
        ORDER BY ce.granted_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                item = _format_row(r)
                tot = item.get("total_lessons", 0) or 0
                comp = item.get("completed_lessons", 0) or 0
                item["progress_percent"] = round((comp / tot * 100)) if tot > 0 else 0
                results.append(item)
            return results


def get_all_enrollments_admin(course_id: int = None):
    """Retrieves all enrollments across students with mobile numbers and course titles for admin."""
    conditions = ["1=1"]
    params = []
    if course_id:
        conditions.append("ce.course_id = %s")
        params.append(course_id)

    query = f"""
        SELECT ce.*, u.name AS user_name, u.email AS user_email, u.mobile_number AS user_mobile,
               c.title AS course_title, c.slug AS course_slug
        FROM course_enrollments ce
        JOIN enrolled_users u ON ce.user_id = u.id
        JOIN courses c ON ce.course_id = c.id
        WHERE {" AND ".join(conditions)}
        ORDER BY ce.created_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def create_or_update_enrollment(user_id: int, course_id: int, status: str = 'active'):
    """
    Grants or updates enrollment status for a user in a course.
    Preserves active enrollment if a pending registration arrives later.
    Self-heals foreign keys if a constraint error is encountered.
    """
    now = datetime.now(timezone.utc)
    query = """
        INSERT INTO course_enrollments (user_id, course_id, status, granted_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, course_id)
        DO UPDATE SET status = CASE
                          WHEN course_enrollments.status = 'active' AND EXCLUDED.status = 'pending'
                          THEN 'active'
                          ELSE EXCLUDED.status
                      END,
                      granted_at = CASE WHEN EXCLUDED.status = 'active' THEN EXCLUDED.granted_at ELSE course_enrollments.granted_at END,
                      updated_at = EXCLUDED.updated_at
        RETURNING id, user_id, course_id, status
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, course_id, status, now, now, now))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            repair_enrolled_users_foreign_keys()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id, course_id, status, now, now, now))
                    row = cur.fetchone()
                conn.commit()
                return dict(row)
        raise


def revoke_enrollment(user_id: int, course_id: int):
    """Revokes active course access for a student."""
    now = datetime.now(timezone.utc)
    query = """
        UPDATE course_enrollments
        SET status = 'revoked', updated_at = %s
        WHERE user_id = %s AND course_id = %s
        RETURNING id, status
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (now, user_id, course_id))
            row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None
