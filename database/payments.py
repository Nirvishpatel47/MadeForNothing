"""
Course Payment Submissions & Manual UPI Verification Database Queries for MADE FOR NOTHING.
Handles 12-digit UTR audits, duplicate payment checks, and admin approvals/rejections.
"""
import logging
from datetime import datetime, timezone
from .connection import get_connection, _format_row
from .schema import repair_enrolled_users_foreign_keys
from .enrollments import create_or_update_enrollment

logger = logging.getLogger("made_for_nothing.database.payments")


def get_payment_submission_by_reference(payment_reference: str):
    """Checks if a UTR / payment reference has already been submitted."""
    ref = (payment_reference or "").strip()
    if not ref:
        return None
    query = """
        SELECT * FROM payment_submissions
        WHERE payment_reference = %s AND status IN ('pending', 'approved')
        ORDER BY submitted_at DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (ref,))
            row = cur.fetchone()
            return _format_row(row)


def create_payment_submission(
    user_id: int,
    course_id: int,
    amount: int,
    payment_reference: str,
    payer_name: str = "",
    payer_note: str = ""
):
    """
    Registers a new UPI payment submission for manual bank auditing.
    Automatically links pending enrollment and self-heals foreign keys if needed.
    """
    now = datetime.now(timezone.utc)
    ref = payment_reference.strip()

    # Register pending enrollment record if not exists (self-heals FK if needed)
    create_or_update_enrollment(user_id, course_id, status="pending")

    query = """
        INSERT INTO payment_submissions (
            user_id, course_id, amount, payment_reference,
            payer_name, payer_note, status, submitted_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
        RETURNING id, user_id, course_id, amount, payment_reference, status, submitted_at
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, course_id, amount, ref, payer_name.strip(), payer_note.strip(), now))
                row = cur.fetchone()
            conn.commit()
            return dict(row)
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            repair_enrolled_users_foreign_keys()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id, course_id, amount, ref, payer_name.strip(), payer_note.strip(), now))
                    row = cur.fetchone()
                conn.commit()
                return dict(row)
        raise


def get_payment_submission_by_id(payment_id: int):
    """Retrieves payment submission with enrolled student and course details."""
    query = """
        SELECT ps.*, u.name AS user_name, u.email AS user_email, u.mobile_number AS user_mobile,
               c.title AS course_title, c.slug AS course_slug
        FROM payment_submissions ps
        JOIN enrolled_users u ON ps.user_id = u.id
        JOIN courses c ON ps.course_id = c.id
        WHERE ps.id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (payment_id,))
            row = cur.fetchone()
            return _format_row(row)


def get_payment_submissions_admin(status: str = None, course_id: int = None):
    """Fetches payment submissions filtered by verification status and course for instructor admin."""
    conditions = ["1=1"]
    params = []
    if status and status != "all":
        conditions.append("ps.status = %s")
        params.append(status)
    if course_id:
        conditions.append("ps.course_id = %s")
        params.append(course_id)

    query = f"""
        SELECT ps.*, u.name AS user_name, u.email AS user_email, u.mobile_number AS user_mobile,
               c.title AS course_title, c.slug AS course_slug
        FROM payment_submissions ps
        JOIN enrolled_users u ON ps.user_id = u.id
        JOIN courses c ON ps.course_id = c.id
        WHERE {" AND ".join(conditions)}
        ORDER BY ps.submitted_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def get_user_payment_for_course(user_id: int, course_id: int):
    """Fetches the latest payment submission of a user for a course."""
    query = """
        SELECT * FROM payment_submissions
        WHERE user_id = %s AND course_id = %s
        ORDER BY submitted_at DESC
        LIMIT 1
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, course_id))
            row = cur.fetchone()
            return _format_row(row)


def approve_payment_submission(payment_id: int, reviewed_by: str = None, admin_note: str = ""):
    """
    Approves a payment submission and grants active course enrollment immediately.
    Self-heals foreign keys if needed.
    """
    now = datetime.now(timezone.utc)
    payment = get_payment_submission_by_id(payment_id)
    if not payment:
        return None

    user_id = payment["user_id"]
    course_id = payment["course_id"]

    query_payment = """
        UPDATE payment_submissions
        SET status = 'approved',
            reviewed_at = %s,
            reviewed_by = %s,
            admin_note = %s
        WHERE id = %s
        RETURNING *
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query_payment, (now, reviewed_by or "admin", admin_note.strip(), payment_id))
                updated_payment = cur.fetchone()

                # Activate course enrollment immediately
                query_enroll = """
                    INSERT INTO course_enrollments (user_id, course_id, status, granted_at, created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s, %s)
                    ON CONFLICT (user_id, course_id)
                    DO UPDATE SET status = 'active', granted_at = %s, updated_at = %s
                """
                cur.execute(query_enroll, (user_id, course_id, now, now, now, now, now))
            conn.commit()
    except Exception as e:
        if "foreign key constraint" in str(e).lower():
            repair_enrolled_users_foreign_keys()
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_payment, (now, reviewed_by or "admin", admin_note.strip(), payment_id))
                    updated_payment = cur.fetchone()
                    query_enroll = """
                        INSERT INTO course_enrollments (user_id, course_id, status, granted_at, created_at, updated_at)
                        VALUES (%s, %s, 'active', %s, %s, %s)
                        ON CONFLICT (user_id, course_id)
                        DO UPDATE SET status = 'active', granted_at = %s, updated_at = %s
                    """
                    cur.execute(query_enroll, (user_id, course_id, now, now, now, now, now))
                conn.commit()
        else:
            raise

    logger.info(f"Payment {payment_id} approved for user {user_id}, course {course_id}")
    return _format_row(updated_payment)


def reject_payment_submission(payment_id: int, reviewed_by: str = None, admin_note: str = ""):
    """Rejects a payment submission with an optional administrative note."""
    now = datetime.now(timezone.utc)
    query = """
        UPDATE payment_submissions
        SET status = 'rejected',
            reviewed_at = %s,
            reviewed_by = %s,
            admin_note = %s
        WHERE id = %s
        RETURNING *
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (now, reviewed_by or "admin", admin_note.strip(), payment_id))
            updated_payment = cur.fetchone()
        conn.commit()

    return _format_row(updated_payment)
