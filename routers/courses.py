"""
Course Discovery & Student Dashboard Routes for MADE FOR NOTHING.
Handles public course listings, detailed syllabus previews, and enrolled student studio dashboard.
"""
import logging
from fastapi import APIRouter, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import db
import auth
import markdown_utils
from core.config import settings

logger = logging.getLogger("made_for_nothing.courses")
router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


@router.get("/course", response_class=HTMLResponse)
@router.get("/courses", response_class=HTMLResponse)
def list_courses(request: Request):
    current_user = auth.get_current_user_optional(request)
    try:
        courses = db.get_published_courses()
    except Exception as e:
        logger.error(f"Error fetching courses: {e}")
        courses = []

    return templates.TemplateResponse("courses_list.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "courses",
        "courses": courses,
        "canonical_url": f"{settings.BASE_URL}/courses",
        "base_url": settings.BASE_URL
    })


@router.get("/courses/dashboard", response_class=HTMLResponse)
@router.get("/course/dashboard", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
def student_dashboard(request: Request):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        return RedirectResponse("/login?next=/courses/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    try:
        enrolled_courses = db.get_user_enrolled_courses(current_user["id"])
        total_completed_units = 0
        total_units = 0

        # Determine next lesson object and order details for each course
        for c in enrolled_courses:
            total_completed_units += c.get("completed_lessons", 0) or 0
            total_units += c.get("total_lessons", 0) or 0

            progress_data = db.get_course_progress_for_user(current_user["id"], c["id"])
            all_lessons = db.get_published_lessons_by_course(c["id"])

            completed_map = {item["lesson_id"]: item["completed"] for item in progress_data.get("lessons", [])}

            next_lesson_obj = None
            for idx, l in enumerate(all_lessons):
                is_comp = completed_map.get(l["id"], False)
                if not is_comp:
                    next_lesson_obj = {
                        "id": l["id"],
                        "title": l["title"],
                        "order_index": idx + 1,
                        "duration_minutes": (l.get("duration_seconds") or 0) // 60 if l.get("duration_seconds") else None
                    }
                    break

            # If all are completed, default to the first lesson for review
            if not next_lesson_obj and all_lessons:
                next_lesson_obj = {
                    "id": all_lessons[0]["id"],
                    "title": all_lessons[0]["title"],
                    "order_index": 1,
                    "duration_minutes": (all_lessons[0].get("duration_seconds") or 0) // 60 if all_lessons[0].get("duration_seconds") else None
                }

            c["next_lesson"] = next_lesson_obj
            c["next_lesson_id"] = next_lesson_obj["id"] if next_lesson_obj else None

        primary_course = enrolled_courses[0] if enrolled_courses else None

        # Pending payments
        all_pending = db.get_payment_submissions_admin(status="pending")
        user_pending = [p for p in all_pending if p["user_id"] == current_user["id"]]
    except Exception as e:
        logger.error(f"Error loading dashboard for user {current_user['id']}: {e}")
        enrolled_courses = []
        user_pending = []
        primary_course = None
        total_completed_units = 0
        total_units = 0

    return templates.TemplateResponse("course_dashboard.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "dashboard",
        "enrolled_courses": enrolled_courses,
        "primary_course": primary_course,
        "total_completed_units": total_completed_units,
        "total_units": total_units,
        "pending_payments": user_pending,
        "canonical_url": f"{settings.BASE_URL}/courses/dashboard",
        "base_url": settings.BASE_URL
    })


@router.get("/course/{course_slug}", response_class=HTMLResponse)
@router.get("/courses/{course_slug}", response_class=HTMLResponse)
def course_detail(request: Request, course_slug: str):
    if course_slug == "dashboard":
        return student_dashboard(request)

    current_user = auth.get_current_user_optional(request)
    try:
        course = db.get_published_course_by_slug(course_slug)
    except Exception as e:
        logger.error(f"Error fetching course {course_slug}: {e}")
        course = None

    if not course:
        try:
            course = db.get_course_by_slug_admin(course_slug)
        except Exception as e:
            logger.error(f"Error fetching draft course {course_slug}: {e}")
            course = None

    if not course:
        from .public import render_404
        return render_404(request)

    lessons = db.get_published_lessons_by_course(course["id"])
    if not lessons:
        try:
            lessons = db.get_all_lessons_admin(course["id"])
        except Exception:
            lessons = []

    is_enrolled = db.is_user_enrolled(current_user["id"], course["id"]) if current_user else False
    pending_payment = db.get_user_payment_for_course(current_user["id"], course["id"]) if (current_user and not is_enrolled) else None

    rendered_description = markdown_utils.render_markdown(course.get("description", ""))
    rendered_learn = markdown_utils.render_markdown(course.get("what_you_will_learn", ""))
    rendered_audience = markdown_utils.render_markdown(course.get("target_audience", ""))
    rendered_instructor = markdown_utils.render_markdown(course.get("instructor_bio", ""))

    first_lesson_id = lessons[0]["id"] if lessons else None
    total_seconds = sum((l.get("duration_seconds") or 0) for l in lessons)
    total_course_minutes = round(total_seconds / 60) if total_seconds else 0

    return templates.TemplateResponse("course_detail.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "courses",
        "course": course,
        "lessons": lessons,
        "total_course_minutes": total_course_minutes,
        "is_enrolled": is_enrolled,
        "pending_payment": pending_payment,
        "first_lesson_id": first_lesson_id,
        "rendered_description": rendered_description,
        "rendered_learn": rendered_learn,
        "rendered_audience": rendered_audience,
        "rendered_instructor": rendered_instructor,
        "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}",
        "base_url": settings.BASE_URL
    })
