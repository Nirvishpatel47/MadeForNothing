"""
Newsletter Subscribers Database Operations for MADE FOR NOTHING.
Handles reader subscription, duplicate reactivation, unsubscription, and subscriber administration.
"""
from .connection import get_connection, _format_row


def add_subscriber(email):
    """Subscribes an email to the research dispatch newsletter, reactivating if previously inactive."""
    if not email:
        raise ValueError("Email is required.")

    email = email.strip().lower()

    if len(email) > 320 or "@" not in email:
        raise ValueError("Invalid email address.")

    insert_query = """
        INSERT INTO newsletter_subscribers (email)
        VALUES (%s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id, email, subscribed_at, is_active
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(insert_query, (email,))
            row = cur.fetchone()

            if row:
                conn.commit()
                return {
                    "success": True,
                    "created": True,
                    "subscriber": dict(row)
                }

            # Already subscribed — reactivate if necessary
            cur.execute("""
                UPDATE newsletter_subscribers
                SET is_active = TRUE
                WHERE email = %s
                RETURNING id, email, subscribed_at, is_active
            """, (email,))

            row = cur.fetchone()

        conn.commit()

    return {
        "success": True,
        "created": False,
        "subscriber": dict(row)
    }


def get_all_subscribers_admin():
    """Retrieves all newsletter subscribers for admin inspection."""
    query = """
        SELECT id, email, subscribed_at, is_active
        FROM newsletter_subscribers
        ORDER BY subscribed_at DESC
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
            return [_format_row(r) for r in rows]


def unsubscribe(email):
    """Deactivates a subscriber."""
    if not email:
        return False
    query = "UPDATE newsletter_subscribers SET is_active = FALSE WHERE email = %s RETURNING id"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (email.strip().lower(),))
            row = cur.fetchone()
        conn.commit()
        return bool(row)
