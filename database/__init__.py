"""
Database Package for MADE FOR NOTHING.
Modularized PostgreSQL access layer covering:
- connection: thread-safe connection pool & row normalization
- schema: table creation DDLs & self-healing constraint migrations
- posts: published articles, landing curation & admin post management
- subscribers: dispatch newsletter registrations & unsubscription
- users: enrolled students, mobile numbers & Firebase auth sync
- courses: courses, syllabus units, Mux asset configuration & Q&As
- enrollments: active student access control & dashboard analytics
- payments: peer-to-peer UPI settlements & 12-digit UTR audits
- progress: video playback tracking & reflection responses
"""
from .connection import (
    get_pool,
    get_connection,
    _format_row,
    VALID_TYPES,
    DATABASE_URL,
    PSYCOPG_VERSION,
)
from .schema import (
    init_db,
    repair_enrolled_users_foreign_keys,
)
from .posts import (
    get_landing_selected_posts,
    get_recent_published_posts,
    get_published_posts,
    get_published_post_by_slug,
    get_continue_reading_posts,
    get_all_published_slugs,
    get_all_posts_admin,
    get_filtered_posts_admin,
    get_post_counts_admin,
    get_post_by_id,
    get_post_by_id_admin,
    get_post_by_slug_admin,
    get_all_posts_for_selector,
    create_post,
    update_post,
    delete_post,
    toggle_publish_status,
    toggle_landing_status,
)
from .subscribers import (
    add_subscriber,
    get_all_subscribers_admin,
    unsubscribe,
)
from .users import (
    create_user,
    get_user_by_firebase_uid,
    get_user_by_email,
    get_user_by_id,
    sync_firebase_user,
    get_all_enrolled_users_admin,
)
from .courses import (
    get_published_courses,
    get_published_course_by_slug,
    get_course_by_id,
    get_course_by_slug_admin,
    get_all_courses_admin,
    create_course,
    update_course,
    delete_course,
    toggle_course_publish_status,
    get_published_lessons_by_course,
    get_all_lessons_admin,
    get_lesson_by_id,
    get_lesson_by_course_and_slug,
    create_lesson,
    update_lesson,
    update_lesson_mux,
    delete_lesson,
    reorder_lessons,
    get_questions_by_lesson,
    create_question,
    update_question,
    delete_question,
    get_question_by_id,
)
from .enrollments import (
    get_enrollment,
    is_user_enrolled,
    get_user_enrolled_courses,
    get_all_enrollments_admin,
    create_or_update_enrollment,
    revoke_enrollment,
)
from .payments import (
    get_payment_submission_by_reference,
    create_payment_submission,
    get_payment_submission_by_id,
    get_payment_submissions_admin,
    get_user_payment_for_course,
    approve_payment_submission,
    reject_payment_submission,
)
from .progress import (
    upsert_student_question_response,
    update_student_question_assessment,
    get_student_responses_for_lesson,
    get_student_responses_for_lesson_admin,
    get_lesson_progress,
    get_course_progress_for_user,
    save_lesson_progress,
)

__all__ = [
    # Connection & Pool
    "get_pool",
    "get_connection",
    "_format_row",
    "VALID_TYPES",
    "DATABASE_URL",
    "PSYCOPG_VERSION",
    # Schema
    "init_db",
    "repair_enrolled_users_foreign_keys",
    # Posts
    "get_landing_selected_posts",
    "get_recent_published_posts",
    "get_published_posts",
    "get_published_post_by_slug",
    "get_continue_reading_posts",
    "get_all_published_slugs",
    "get_all_posts_admin",
    "get_filtered_posts_admin",
    "get_post_counts_admin",
    "get_post_by_id",
    "get_post_by_id_admin",
    "get_post_by_slug_admin",
    "get_all_posts_for_selector",
    "create_post",
    "update_post",
    "delete_post",
    "toggle_publish_status",
    "toggle_landing_status",
    # Subscribers
    "add_subscriber",
    "get_all_subscribers_admin",
    "unsubscribe",
    # Users
    "create_user",
    "get_user_by_firebase_uid",
    "get_user_by_email",
    "get_user_by_id",
    "sync_firebase_user",
    "get_all_enrolled_users_admin",
    # Courses & Lessons
    "get_published_courses",
    "get_published_course_by_slug",
    "get_course_by_id",
    "get_course_by_slug_admin",
    "get_all_courses_admin",
    "create_course",
    "update_course",
    "delete_course",
    "toggle_course_publish_status",
    "get_published_lessons_by_course",
    "get_all_lessons_admin",
    "get_lesson_by_id",
    "get_lesson_by_course_and_slug",
    "create_lesson",
    "update_lesson",
    "update_lesson_mux",
    "delete_lesson",
    "reorder_lessons",
    "get_questions_by_lesson",
    "create_question",
    "update_question",
    "delete_question",
    "get_question_by_id",
    # Enrollments
    "get_enrollment",
    "is_user_enrolled",
    "get_user_enrolled_courses",
    "get_all_enrollments_admin",
    "create_or_update_enrollment",
    "revoke_enrollment",
    # Payments
    "get_payment_submission_by_reference",
    "create_payment_submission",
    "get_payment_submission_by_id",
    "get_payment_submissions_admin",
    "get_user_payment_for_course",
    "approve_payment_submission",
    "reject_payment_submission",
    # Progress & Responses
    "upsert_student_question_response",
    "update_student_question_assessment",
    "get_student_responses_for_lesson",
    "get_student_responses_for_lesson_admin",
    "get_lesson_progress",
    "get_course_progress_for_user",
    "save_lesson_progress",
]
