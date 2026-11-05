"""
Database Schema Initialization & Self-Healing Migrations for MADE FOR NOTHING.
Executes table creation DDLs, column additions, indexes, and foreign key constraint repairs.
"""
import logging
from .connection import get_connection

logger = logging.getLogger("made_for_nothing.database.schema")


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
        continue_reading_slugs TEXT[] DEFAULT '{}',
        featured_image_url TEXT,
        featured_image_key TEXT,
        featured_image_alt VARCHAR(255),
        featured_image_width INTEGER,
        featured_image_height INTEGER,
        featured_image_size INTEGER,
        featured_image_mime VARCHAR(50),
        featured_image_filename VARCHAR(255)
    );

    CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id SERIAL PRIMARY KEY,
        email VARCHAR(320) NOT NULL UNIQUE,
        subscribed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    );

    CREATE INDEX IF NOT EXISTS idx_newsletter_subscribers_email
    ON newsletter_subscribers (email);

    CREATE INDEX IF NOT EXISTS idx_newsletter_subscribers_active
    ON newsletter_subscribers (is_active);

    -- Schema evolution without external .sql files
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS show_on_landing BOOLEAN DEFAULT FALSE;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_url TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_key TEXT;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_alt VARCHAR(255);
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_width INTEGER;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_height INTEGER;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_size INTEGER;
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_mime VARCHAR(50);
    ALTER TABLE posts ADD COLUMN IF NOT EXISTS featured_image_filename VARCHAR(255);

    CREATE INDEX IF NOT EXISTS idx_posts_type_published ON posts (type, is_published, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_slug ON posts (slug);
    CREATE INDEX IF NOT EXISTS idx_posts_published ON posts (is_published, published_at DESC);
    CREATE INDEX IF NOT EXISTS idx_posts_landing ON posts (show_on_landing, is_published, published_at DESC);

    -- =========================================================================
    -- COURSE SYSTEM SCHEMA
    -- =========================================================================

    CREATE TABLE IF NOT EXISTS enrolled_users (
        id SERIAL PRIMARY KEY,
        email VARCHAR(320) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL DEFAULT '',
        name VARCHAR(255) NOT NULL,
        mobile_number VARCHAR(32) DEFAULT '',
        firebase_uid VARCHAR(128),
        email_verified BOOLEAN NOT NULL DEFAULT FALSE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    ALTER TABLE enrolled_users ADD COLUMN IF NOT EXISTS mobile_number VARCHAR(32) DEFAULT '';
    ALTER TABLE enrolled_users ADD COLUMN IF NOT EXISTS firebase_uid VARCHAR(128);
    ALTER TABLE enrolled_users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

    CREATE TABLE IF NOT EXISTS courses (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL UNIQUE,
        subtitle VARCHAR(500) DEFAULT '',
        description TEXT DEFAULT '',
        what_you_will_learn TEXT DEFAULT '',
        target_audience TEXT DEFAULT '',
        price INTEGER NOT NULL DEFAULT 0,
        thumbnail VARCHAR(500) DEFAULT '',
        is_published BOOLEAN NOT NULL DEFAULT FALSE,
        faq JSONB DEFAULT '[]'::jsonb,
        instructor_bio TEXT DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS course_lessons (
        id SERIAL PRIMARY KEY,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        slug VARCHAR(255) NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0,
        description TEXT DEFAULT '',
        content_markdown TEXT DEFAULT '',
        mux_asset_id VARCHAR(255) DEFAULT '',
        mux_playback_id VARCHAR(255) DEFAULT '',
        mux_upload_id VARCHAR(255) DEFAULT '',
        mux_status VARCHAR(50) DEFAULT 'none',
        duration_seconds INTEGER DEFAULT 0,
        is_published BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(course_id, slug)
    );

    CREATE TABLE IF NOT EXISTS course_questions (
        id SERIAL PRIMARY KEY,
        lesson_id INTEGER NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS course_enrollments (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        granted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, course_id)
    );

    CREATE TABLE IF NOT EXISTS payment_submissions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
        course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        amount INTEGER NOT NULL,
        payment_reference VARCHAR(255) NOT NULL,
        payer_name VARCHAR(255) DEFAULT '',
        payer_note TEXT DEFAULT '',
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        submitted_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMPTZ,
        reviewed_by VARCHAR(255),
        admin_note TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS lesson_progress (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
        lesson_id INTEGER NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
        completed BOOLEAN NOT NULL DEFAULT FALSE,
        last_position_seconds INTEGER NOT NULL DEFAULT 0,
        completed_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, lesson_id)
    );

    CREATE TABLE IF NOT EXISTS student_question_responses (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES enrolled_users(id) ON DELETE CASCADE,
        question_id INTEGER NOT NULL REFERENCES course_questions(id) ON DELETE CASCADE,
        lesson_id INTEGER NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
        student_answer TEXT NOT NULL,
        self_assessment VARCHAR(50) DEFAULT NULL,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, question_id)
    );

    CREATE INDEX IF NOT EXISTS idx_enrolled_users_email ON enrolled_users (email);
    CREATE INDEX IF NOT EXISTS idx_courses_slug ON courses (slug);
    CREATE INDEX IF NOT EXISTS idx_courses_published ON courses (is_published, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_course_lessons_course ON course_lessons (course_id, order_index);
    CREATE INDEX IF NOT EXISTS idx_course_questions_lesson ON course_questions (lesson_id, sort_order);
    CREATE INDEX IF NOT EXISTS idx_enrollments_user_id ON course_enrollments (user_id);
    CREATE INDEX IF NOT EXISTS idx_enrollments_course_id ON course_enrollments (course_id);
    CREATE INDEX IF NOT EXISTS idx_payment_submissions_status ON payment_submissions (status);
    CREATE INDEX IF NOT EXISTS idx_payment_submissions_course ON payment_submissions (course_id);
    CREATE INDEX IF NOT EXISTS idx_payment_submissions_user ON payment_submissions (user_id);
    CREATE INDEX IF NOT EXISTS idx_payment_submissions_ref ON payment_submissions (payment_reference);
    CREATE INDEX IF NOT EXISTS idx_lesson_progress_user ON lesson_progress (user_id);
    CREATE INDEX IF NOT EXISTS idx_lesson_progress_lesson ON lesson_progress (lesson_id);
    CREATE INDEX IF NOT EXISTS idx_student_responses_user ON student_question_responses (user_id);
    CREATE INDEX IF NOT EXISTS idx_student_responses_question ON student_question_responses (question_id);
    CREATE INDEX IF NOT EXISTS idx_student_responses_lesson ON student_question_responses (lesson_id);
    """
    statements = [s.strip() for s in create_table_query.split(";") if s.strip()]
    with get_connection() as conn:
        for stmt in statements:
            try:
                with conn.cursor() as cur:
                    cur.execute(stmt)
                conn.commit()
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.debug(f"init_db statement skipped or already applied: {e}")

    repair_enrolled_users_foreign_keys()
    repair_post_image_urls()
    logger.info("Database schema initialized successfully.")


def repair_enrolled_users_foreign_keys():
    """
    Ensures foreign keys on course_enrollments, payment_submissions,
    lesson_progress, and student_question_responses reference enrolled_users(id)
    rather than any legacy users(id) table.
    """
    fk_migrations = [
        (
            "course_enrollments",
            "course_enrollments_user_id_fkey",
            "ALTER TABLE course_enrollments DROP CONSTRAINT IF EXISTS course_enrollments_user_id_fkey",
            "ALTER TABLE course_enrollments ADD CONSTRAINT course_enrollments_user_id_fkey FOREIGN KEY (user_id) REFERENCES enrolled_users(id) ON DELETE CASCADE NOT VALID"
        ),
        (
            "payment_submissions",
            "payment_submissions_user_id_fkey",
            "ALTER TABLE payment_submissions DROP CONSTRAINT IF EXISTS payment_submissions_user_id_fkey",
            "ALTER TABLE payment_submissions ADD CONSTRAINT payment_submissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES enrolled_users(id) ON DELETE CASCADE NOT VALID"
        ),
        (
            "lesson_progress",
            "lesson_progress_user_id_fkey",
            "ALTER TABLE lesson_progress DROP CONSTRAINT IF EXISTS lesson_progress_user_id_fkey",
            "ALTER TABLE lesson_progress ADD CONSTRAINT lesson_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES enrolled_users(id) ON DELETE CASCADE NOT VALID"
        ),
        (
            "student_question_responses",
            "student_question_responses_user_id_fkey",
            "ALTER TABLE student_question_responses DROP CONSTRAINT IF EXISTS student_question_responses_user_id_fkey",
            "ALTER TABLE student_question_responses ADD CONSTRAINT student_question_responses_user_id_fkey FOREIGN KEY (user_id) REFERENCES enrolled_users(id) ON DELETE CASCADE NOT VALID"
        ),
    ]
    with get_connection() as conn:
        for table_name, constraint_name, drop_sql, add_sql in fk_migrations:
            try:
                with conn.cursor() as cur:
                    cur.execute(drop_sql)
                    cur.execute(add_sql)
                conn.commit()
            except Exception as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.debug(f"FK repair skipped for {table_name}.{constraint_name}: {e}")


def repair_post_image_urls():
    """
    Cleans up any legacy private S3 endpoint URLs (r2.cloudflarestorage.com) stored in posts
    and ensures valid object keys and working public/media URLs.
    """
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, featured_image_url, featured_image_key
                    FROM posts
                    WHERE featured_image_url LIKE '%r2.cloudflarestorage.com%'
                       OR (featured_image_key IS NULL AND featured_image_url IS NOT NULL AND featured_image_url != '')
                """)
                rows = cur.fetchall()
                for row in rows:
                    p_id = row["id"]
                    url = (row["featured_image_url"] or "").strip()
                    key = (row.get("featured_image_key") or "").strip()
                    if not key and "/images/" in url:
                        idx = url.find("images/")
                        if idx != -1:
                            key = url[idx:]
                    elif not key and url.startswith("images/"):
                        key = url

                    if key:
                        from r2_storage import build_public_url
                        new_url = build_public_url(key)
                        cur.execute("""
                            UPDATE posts
                            SET featured_image_key = %s,
                                featured_image_url = %s,
                                featured_image_width = COALESCE(featured_image_width, 1280),
                                featured_image_height = COALESCE(featured_image_height, 720)
                            WHERE id = %s
                        """, (key, new_url, p_id))
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.debug(f"Image URL repair skipped or failed: {e}")
