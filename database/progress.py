"""
Lesson Progress & Student Q&A Reflections Database Operations for MADE FOR NOTHING.
Tracks watch positions, unit completions, and submitted checkpoint reflections.
"""
from datetime import datetime, timezone
from .connection import get_connection, _format_row
from .schema import repair_enrolled_users_foreign_keys


def upsert_student_question_response(
    user_id: int,
    question_id: int,
    lesson_id: int,
    student_answer: str,
    self_assessment: str = None
):
    """Saves or updates a student's answer to a curriculum reflection question."""
    now = datetime.now(timezone.utc)
    query = """
        INSERT INTO student_question_responses (
            user_id, question_id, lesson_id, student_answer, self_assessment, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, question_id)
        DO UPDATE SET student_answer = EXCLUDED.student_answer,
                      lesson_id = EXCLUDED.lesson_id,
                      self_assessment = COALESCE(EXCLUDED.self_assessment, student_question_responses.self_assessment),
                      updated_at = EXCLUDED.updated_at
        RETURNING *
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, question_id, lesson_id, student_answer.strip(), self_assessment, now, now))
                row = cur.fetchone()
            conn.commit()
            return _format_row(row)
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            repair_enrolled_users_foreign_keys()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id, question_id, lesson_id, student_answer.strip(), self_assessment, now, now))
                    row = cur.fetchone()
                conn.commit()
                return _format_row(row)
        raise


def update_student_question_assessment(user_id: int, question_id: int, self_assessment: str):
    """Updates self-assessment evaluation for a student answer (pass, review, mastered)."""
    now = datetime.now(timezone.utc)
    query = """
        UPDATE student_question_responses
        SET self_assessment = %s, updated_at = %s
        WHERE user_id = %s AND question_id = %s
        RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (self_assessment.strip(), now, user_id, question_id))
            row = cur.fetchone()
        conn.commit()
        return _format_row(row) if row else None


def get_student_responses_for_lesson(user_id: int, lesson_id: int):
    """Returns a dictionary of student responses for a given lesson keyed by question_id."""
    query = """
        SELECT * FROM student_question_responses
        WHERE user_id = %s AND lesson_id = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, lesson_id))
            rows = cur.fetchall()
            res = {}
            for r in rows:
                formatted = _format_row(r)
                res[formatted["question_id"]] = formatted
            return res


def get_student_responses_for_lesson_admin(lesson_id: int):
    """Fetches all student responses for a lesson for instructor review."""
    query = """
        SELECT sqr.*, u.name AS user_name, u.email AS user_email
        FROM student_question_responses sqr
        JOIN enrolled_users u ON sqr.user_id = u.id
        WHERE sqr.lesson_id = %s
        ORDER BY sqr.updated_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (lesson_id,))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_lesson_progress(user_id: int, lesson_id: int):
    """Retrieves watch progress and completion status for a lesson."""
    query = "SELECT * FROM lesson_progress WHERE user_id = %s AND lesson_id = %s LIMIT 1"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, lesson_id))
            row = cur.fetchone()
            return _format_row(row)


def get_course_progress_for_user(user_id: int, course_id: int):
    """Calculates completion metrics and lesson breakdown for an enrolled course."""
    query = """
        SELECT cl.id AS lesson_id, cl.title, cl.order_index,
               COALESCE(lp.completed, FALSE) AS completed,
               COALESCE(lp.last_position_seconds, 0) AS last_position_seconds,
               lp.completed_at
        FROM course_lessons cl
        LEFT JOIN lesson_progress lp ON cl.id = lp.lesson_id AND lp.user_id = %s
        WHERE cl.course_id = %s AND cl.is_published = TRUE
        ORDER BY cl.order_index ASC, cl.id ASC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, course_id))
            rows = cur.fetchall()
            items = [_format_row(r) for r in rows]
            total = len(items)
            completed_count = sum(1 for i in items if i.get("completed"))
            percent = round((completed_count / total * 100)) if total > 0 else 0
            return {
                "lessons": items,
                "total_lessons": total,
                "completed_count": completed_count,
                "progress_percent": percent
            }


def save_lesson_progress(
    user_id: int,
    lesson_id: int,
    completed: bool = None,
    last_position_seconds: int = None
):
    """
    Updates or creates a lesson progress record with watch position and completion flag.
    Self-heals foreign keys if needed.
    """
    now = datetime.now(timezone.utc)
    current = get_lesson_progress(user_id, lesson_id)

    new_completed = current.get("completed", False) if current else False
    if completed is not None:
        new_completed = bool(completed)

    completed_at = current.get("completed_at") if current else None
    if new_completed and not completed_at:
        completed_at = now
    elif not new_completed:
        completed_at = None

    pos = current.get("last_position_seconds", 0) if current else 0
    if last_position_seconds is not None:
        pos = max(0, int(last_position_seconds))

    query = """
        INSERT INTO lesson_progress (user_id, lesson_id, completed, last_position_seconds, completed_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, lesson_id)
        DO UPDATE SET completed = EXCLUDED.completed,
                      last_position_seconds = EXCLUDED.last_position_seconds,
                      completed_at = EXCLUDED.completed_at,
                      updated_at = EXCLUDED.updated_at
        RETURNING id, user_id, lesson_id, completed, last_position_seconds
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, lesson_id, new_completed, pos, completed_at, now))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            repair_enrolled_users_foreign_keys()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id, lesson_id, new_completed, pos, completed_at, now))
                    row = cur.fetchone()
                conn.commit()
                return dict(row)
        raise
