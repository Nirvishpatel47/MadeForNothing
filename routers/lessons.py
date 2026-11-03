"""
Lesson Player & Interactive Learning APIs for MADE FOR NOTHING.
Handles protected lesson curriculum delivery, video playback token generation,
progress telemetry, reflection submission, and self-assessment checks.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
import auth
import markdown_utils
import mux_utils
from core.config import settings

logger = logging.getLogger("made_for_nothing.lessons")
router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


# --- Pydantic Schemas for Lesson Telemetry & Responses ---

class LessonProgressUpdate(BaseModel):
    completed: Optional[bool] = None
    last_position_seconds: Optional[int] = None


class StudentQuestionSubmission(BaseModel):
    answer: str


class StudentAssessmentUpdate(BaseModel):
    assessment: str


# --- Protected Lesson Views ---

@router.get("/course/{course_slug}/lessons/{lesson_id}", response_class=HTMLResponse)
@router.get("/courses/{course_slug}/lessons/{lesson_id}", response_class=HTMLResponse)
def lesson_view(request: Request, course_slug: str, lesson_id: int):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(
            f"/login?next=/courses/{course_slug}/lessons/{lesson_id}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson or lesson.get("course_slug") != course_slug or not lesson.get("is_published"):
        from .public import render_404
        return render_404(request)

    # Strict access control verification
    if not db.is_user_enrolled(current_user["id"], lesson["course_id"]):
        logger.warning(f"Unauthorized lesson access attempt: user {current_user['id']} to lesson {lesson_id}")
        return RedirectResponse(f"/courses/{course_slug}", status_code=status.HTTP_303_SEE_OTHER)

    course = db.get_course_by_id(lesson["course_id"])
    all_lessons = db.get_published_lessons_by_course(lesson["course_id"])
    progress_map = db.get_course_progress_for_user(current_user["id"], lesson["course_id"])
    completed_lesson_ids = {i["lesson_id"] for i in progress_map["lessons"] if i["completed"]}

    for l in all_lessons:
        l["completed"] = l["id"] in completed_lesson_ids

    # Find prev and next lesson
    prev_lesson = None
    next_lesson = None
    lesson_order_index = 1
    for idx, l in enumerate(all_lessons):
        if l["id"] == lesson["id"]:
            lesson_order_index = idx + 1
            if idx > 0:
                prev_lesson = all_lessons[idx - 1]
            if idx < len(all_lessons) - 1:
                next_lesson = all_lessons[idx + 1]
            break

    lesson_prog = db.get_lesson_progress(current_user["id"], lesson_id)
    is_completed = lesson_prog.get("completed", False) if lesson_prog else False

    questions = db.get_questions_by_lesson(lesson_id)
    student_responses = db.get_student_responses_for_lesson(current_user["id"], lesson_id)
    rendered_content = markdown_utils.render_markdown(lesson.get("content_markdown", ""))

    return templates.TemplateResponse("course_lesson.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "courses",
        "course": course,
        "lesson": lesson,
        "all_lessons": all_lessons,
        "lesson_order_index": lesson_order_index,
        "prev_lesson": prev_lesson,
        "next_lesson": next_lesson,
        "progress": lesson_prog or {},
        "is_completed": is_completed,
        "questions": questions,
        "student_responses": student_responses,
        "rendered_content": rendered_content,
        "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}/lessons/{lesson_id}",
        "base_url": settings.BASE_URL
    })


# --- Signed Playback & Telemetry APIs ---

@router.get("/api/course/lessons/{lesson_id}/playback")
@router.get("/api/course/lessons/{lesson_id}/playback-token")
@router.get("/api/courses/lessons/{lesson_id}/playback")
@router.get("/api/courses/lessons/{lesson_id}/playback-token")
def get_lesson_playback_token(request: Request, lesson_id: int):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson or not lesson.get("is_published"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")

    if not db.is_user_enrolled(current_user["id"], lesson["course_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active enrollment required for playback.")

    playback_id = lesson.get("mux_playback_id")
    if not playback_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No video asset linked to this lesson.")

    tokens = mux_utils.generate_all_tokens(playback_id, expiration_seconds=7200)

    return {
        "success": True,
        "playback_id": playback_id,
        "token": tokens.get("playback"),
        "thumbnail_token": tokens.get("thumbnail"),
        "storyboard_token": tokens.get("storyboard")
    }


@router.post("/api/course/lessons/{lesson_id}/progress")
def update_lesson_progress(request: Request, lesson_id: int, data: LessonProgressUpdate):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")

    if not db.is_user_enrolled(current_user["id"], lesson["course_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course.")

    result = db.save_lesson_progress(
        user_id=current_user["id"],
        lesson_id=lesson_id,
        completed=data.completed,
        last_position_seconds=data.last_position_seconds
    )
    return {"success": True, "progress": result}


@router.post("/api/course/lessons/{lesson_id}/questions/{question_id}/response")
def submit_question_response(
    request: Request,
    lesson_id: int,
    question_id: int,
    data: StudentQuestionSubmission
):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")

    if not db.is_user_enrolled(current_user["id"], lesson["course_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active enrollment required to submit answers.")

    q = db.get_question_by_id(question_id)
    if not q or q["lesson_id"] != lesson_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in this unit.")

    ans_clean = data.answer.strip()
    if not ans_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer cannot be empty.")

    saved = db.upsert_student_question_response(
        user_id=current_user["id"],
        question_id=question_id,
        lesson_id=lesson_id,
        student_answer=ans_clean
    )

    return {
        "success": True,
        "response": saved,
        "instructor_answer": q["answer"]
    }


@router.post("/api/course/lessons/{lesson_id}/questions/{question_id}/assessment")
def update_question_assessment(
    request: Request,
    lesson_id: int,
    question_id: int,
    data: StudentAssessmentUpdate
):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson or not db.is_user_enrolled(current_user["id"], lesson["course_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized.")

    assessment_clean = data.assessment.strip().lower()
    if assessment_clean not in ["pass", "review", "mastered"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assessment option.")

    saved = db.update_student_question_assessment(
        user_id=current_user["id"],
        question_id=question_id,
        self_assessment=assessment_clean
    )

    return {"success": True, "response": saved}


@router.post("/api/webhooks/mux")
async def mux_webhook_handler(request: Request):
    """Mux webhook receiver for automated video encoding status sync."""
    try:
        payload = await request.json()
        event_type = payload.get("type")
        data = payload.get("data", {})

        if event_type == "video.asset.ready":
            asset_id = data.get("id")
            playback_ids = data.get("playback_ids", [])
            duration = data.get("duration")

            signed_id = None
            for p in playback_ids:
                if p.get("policy") == "signed":
                    signed_id = p.get("id")
                    break
            if not signed_id and playback_ids:
                signed_id = playback_ids[0].get("id")

            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE course_lessons
                        SET mux_status = 'ready',
                            mux_playback_id = COALESCE(NULLIF(%s, ''), mux_playback_id),
                            duration_seconds = COALESCE(%s, duration_seconds),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE mux_asset_id = %s
                        """,
                        (signed_id, round(float(duration)) if duration else None, asset_id)
                    )
                conn.commit()
            logger.info(f"Mux asset ready webhook processed for {asset_id}")

        return {"received": True}
    except Exception as e:
        logger.error(f"Error handling Mux webhook: {e}")
        return {"received": False, "error": str(e)}


@router.get("/BingSiteAuth.xml")
async def bing_verification():
    return FileResponse("BingSiteAuth.xml", media_type="application/xml")
