"""
Payment & Settlement Routes for MADE FOR NOTHING.
Handles direct peer-to-peer UPI transfer instructions, QR code generation,
and 12-digit UTR transaction reference audit submissions with robust validation.
"""
import re
import logging
from fastapi import APIRouter, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import db
import auth
from core.config import settings

logger = logging.getLogger("made_for_nothing.payments")
router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


@router.get("/course/{course_slug}/enroll", response_class=HTMLResponse)
@router.get("/courses/{course_slug}/enroll", response_class=HTMLResponse)
def course_payment_page(request: Request, course_slug: str):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(f"/login?next=/courses/{course_slug}/enroll", status_code=status.HTTP_303_SEE_OTHER)

    course = db.get_published_course_by_slug(course_slug)
    if not course:
        try:
            course = db.get_course_by_slug_admin(course_slug)
        except Exception:
            course = None

    if not course:
        from .public import render_404
        return render_404(request)

    # If already actively enrolled, redirect to syllabus
    if db.is_user_enrolled(current_user["id"], course["id"]):
        return RedirectResponse(f"/courses/{course_slug}", status_code=status.HTTP_303_SEE_OTHER)

    existing_pending = db.get_user_payment_for_course(current_user["id"], course["id"])
    if existing_pending and existing_pending.get("status") != "pending":
        existing_pending = None

    return templates.TemplateResponse("course_payment.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "courses",
        "course": course,
        "upi_id": settings.COURSE_UPI_ID,
        "payment_name": settings.COURSE_PAYMENT_NAME,
        "existing_pending": existing_pending,
        "error_message": None,
        "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}/enroll",
        "base_url": settings.BASE_URL
    })


@router.post("/course/{course_slug}/payment", response_class=HTMLResponse)
@router.post("/courses/{course_slug}/payment", response_class=HTMLResponse)
async def submit_payment_action(
    request: Request,
    course_slug: str,
    payment_reference: str = Form(...),
    payer_name: str = Form(""),
    payer_note: str = Form("")
):
    current_user = auth.get_current_user_optional(request)
    if not current_user:
        return RedirectResponse(f"/login?next=/courses/{course_slug}/enroll", status_code=status.HTTP_303_SEE_OTHER)

    course = db.get_published_course_by_slug(course_slug)
    if not course:
        try:
            course = db.get_course_by_slug_admin(course_slug)
        except Exception:
            course = None

    if not course:
        from .public import render_404
        return render_404(request)

    raw_ref = (payment_reference or "").strip()
    ref_clean = re.sub(r"[\s\-]", "", raw_ref)

    # Strict 12-digit UTR validation
    if not ref_clean or not ref_clean.isdigit() or len(ref_clean) != 12:
        err_msg = "A 12-digit UTR number is compulsory. Please enter a valid 12-digit numeric UTR."
        return templates.TemplateResponse("course_payment.html", {
            "request": request,
            "current_user": current_user,
            "current_type": "courses",
            "course": course,
            "upi_id": settings.COURSE_UPI_ID,
            "payment_name": settings.COURSE_PAYMENT_NAME,
            "existing_pending": None,
            "submitted_reference": raw_ref,
            "submitted_payer_name": payer_name.strip(),
            "submitted_payer_note": payer_note.strip(),
            "error_message": err_msg,
            "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}/enroll",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)

    # Check for duplicate UTR submissions
    try:
        existing_ref = db.get_payment_submission_by_reference(ref_clean)
    except Exception:
        existing_ref = None

    if existing_ref:
        if existing_ref.get("user_id") == current_user["id"] and existing_ref.get("course_id") == course["id"]:
            return RedirectResponse(f"/courses/{course_slug}/enroll", status_code=status.HTTP_303_SEE_OTHER)
        return templates.TemplateResponse("course_payment.html", {
            "request": request,
            "current_user": current_user,
            "current_type": "courses",
            "course": course,
            "upi_id": settings.COURSE_UPI_ID,
            "payment_name": settings.COURSE_PAYMENT_NAME,
            "existing_pending": None,
            "submitted_reference": raw_ref,
            "submitted_payer_name": payer_name.strip(),
            "submitted_payer_note": payer_note.strip(),
            "error_message": "This 12-digit UTR reference has already been submitted and is currently under verification.",
            "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}/enroll",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)

    course_price = course.get("price", 0)

    try:
        db.create_payment_submission(
            user_id=current_user["id"],
            course_id=course["id"],
            amount=course_price,
            payment_reference=ref_clean,
            payer_name=payer_name.strip() or current_user.get("name", ""),
            payer_note=payer_note.strip()
        )
        return RedirectResponse(f"/courses/{course_slug}/enroll", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to submit payment for user {current_user['id']}, course {course['id']}: {e}")
        return templates.TemplateResponse("course_payment.html", {
            "request": request,
            "current_user": current_user,
            "current_type": "courses",
            "course": course,
            "upi_id": settings.COURSE_UPI_ID,
            "payment_name": settings.COURSE_PAYMENT_NAME,
            "existing_pending": None,
            "submitted_reference": raw_ref,
            "submitted_payer_name": payer_name.strip(),
            "submitted_payer_note": payer_note.strip(),
            "error_message": "We could not record your payment reference right now. Please verify your 12-digit UTR and try again.",
            "canonical_url": f"{settings.BASE_URL}/courses/{course_slug}/enroll",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)
