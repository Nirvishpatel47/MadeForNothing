"""
Enrolled Users Database Operations for MADE FOR NOTHING.
Handles student user creation, Firebase Authentication synchronization,
profile updates, and administrative student management.
"""
import logging
from datetime import datetime, timezone
from .connection import get_connection, _format_row
from .schema import init_db

logger = logging.getLogger("made_for_nothing.database.users")


def create_user(
    email: str,
    password_hash: str,
    name: str,
    mobile_number: str = "",
    firebase_uid: str = None,
    email_verified: bool = False
):
    """Creates a new student record in enrolled_users with mobile number and verification state."""
    email = email.strip().lower()
    name = name.strip()
    mobile_number = (mobile_number or "").strip()
    now = datetime.now(timezone.utc)
    query = """
        INSERT INTO enrolled_users (
            email, password_hash, name, mobile_number, firebase_uid, email_verified, is_active, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, %s)
        RETURNING id, email, name, mobile_number, firebase_uid, email_verified, is_active, created_at
    """
    params = (email, password_hash, name, mobile_number, firebase_uid, bool(email_verified), now, now)
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
            conn.commit()
            return _format_row(row)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            err_lower = str(e).lower()
            if "enrolled_users" in err_lower or "mobile_number" in err_lower or "firebase_uid" in err_lower:
                init_db()
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    row = cur.fetchone()
                conn.commit()
                return _format_row(row)
            raise


def get_user_by_firebase_uid(firebase_uid: str):
    """Finds a user by their unique Firebase Authentication UID."""
    if not firebase_uid:
        return None
    uid_clean = firebase_uid.strip()
    query = "SELECT * FROM enrolled_users WHERE firebase_uid = %s LIMIT 1"
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, (uid_clean,))
                row = cur.fetchone()
                return _format_row(row)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.debug(f"Error fetching user by firebase_uid: {e}")
            return None


def get_user_by_email(email: str):
    """Finds a user by email address (case-insensitive)."""
    if not email:
        return None
    email = email.strip().lower()
    query = "SELECT * FROM enrolled_users WHERE email = %s LIMIT 1"
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, (email,))
                row = cur.fetchone()
                return _format_row(row)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if "enrolled_users" in str(e).lower() and ("does not exist" in str(e).lower() or "not found" in str(e).lower()):
                try:
                    init_db()
                    with conn.cursor() as cur:
                        cur.execute(query, (email,))
                        row = cur.fetchone()
                        return _format_row(row)
                except Exception:
                    return None
            logger.error(f"Error fetching user by email {email}: {e}")
            return None


def get_user_by_id(user_id: int):
    """Finds a user by primary key ID."""
    if not user_id:
        return None
    query = """
        SELECT id, email, name, mobile_number, firebase_uid, email_verified, is_active, created_at, updated_at
        FROM enrolled_users
        WHERE id = %s
        LIMIT 1
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(query, (user_id,))
                row = cur.fetchone()
                return _format_row(row)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            if "mobile_number" in str(e).lower() or "firebase_uid" in str(e).lower():
                init_db()
                with conn.cursor() as cur:
                    cur.execute(query, (user_id,))
                    row = cur.fetchone()
                    return _format_row(row)
            raise


def sync_firebase_user(
    email: str,
    name: str = "",
    mobile_number: str = "",
    firebase_uid: str = None,
    email_verified: bool = False,
    password_hash: str = ""
):
    """
    Creates or updates a user record in Supabase synced with Firebase Authentication without creating duplicates.
    Preserves custom names, mobile numbers, and password hashes.
    """
    email_clean = email.strip().lower()
    name_clean = (name or "").strip()
    mobile_clean = (mobile_number or "").strip()
    uid_clean = (firebase_uid or "").strip() or None
    now = datetime.now(timezone.utc)

    # Match by email first (primary unique constraint in enrolled_users), then by firebase_uid
    existing = get_user_by_email(email_clean)
    if not existing and uid_clean:
        existing = get_user_by_firebase_uid(uid_clean)

    if existing:
        existing_name = (existing.get("name") or "").strip()
        email_prefix = email_clean.split("@")[0]
        if existing_name and existing_name != email_prefix:
            updated_name = existing_name
        else:
            updated_name = name_clean or existing_name or email_prefix

        updated_mobile = mobile_clean or existing.get("mobile_number") or ""
        updated_uid = uid_clean or existing.get("firebase_uid")
        updated_verified = bool(email_verified or existing.get("email_verified", False))
        updated_pwd = password_hash or existing.get("password_hash") or ""

        query = """
            UPDATE enrolled_users
            SET name = %s,
                mobile_number = %s,
                firebase_uid = %s,
                email_verified = %s,
                password_hash = %s,
                updated_at = %s
            WHERE id = %s
            RETURNING id, email, name, mobile_number, firebase_uid, email_verified, is_active, created_at, updated_at
        """
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    (updated_name, updated_mobile, updated_uid, updated_verified, updated_pwd, now, existing["id"])
                )
                row = cur.fetchone()
            conn.commit()
            return _format_row(row)
    else:
        default_name = name_clean or email_clean.split("@")[0]
        return create_user(
            email=email_clean,
            password_hash=password_hash or "",
            name=default_name,
            mobile_number=mobile_clean,
            firebase_uid=uid_clean,
            email_verified=email_verified
        )


def get_all_enrolled_users_admin():
    """Lists all enrolled users with their active enrolled courses count for administrative view."""
    query = """
        SELECT u.id, u.email, u.name, u.mobile_number, u.firebase_uid, u.email_verified, u.is_active, u.created_at,
               COUNT(ce.id) FILTER (WHERE ce.status = 'active') AS active_courses_count
        FROM enrolled_users u
        LEFT JOIN course_enrollments ce ON u.id = ce.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]
