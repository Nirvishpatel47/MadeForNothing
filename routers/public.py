"""
Public Editorial & Content Routes for MADE FOR NOTHING.
Handles landing page, about page, topic archives (writing, research, experiments, projects, books),
single post reader, sitemap.xml, robots.txt, and newsletter signups.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Response, status
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

import db
import markdown_utils
import auth
from core.config import settings, TYPE_METADATA, ARCHIVE_SECTIONS

logger = logging.getLogger("made_for_nothing.public")
router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


class NewsletterSignup(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Invalid email address format.")
        return value


def render_404(request: Request) -> HTMLResponse:
    """Renders the editorial 404 error page with recent articles."""
    current_user = auth.get_current_user_optional(request)
    try:
        recent_posts = db.get_recent_published_posts(limit=4)
        for p in recent_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))
    except Exception as e:
        logger.warning(f"Error fetching recent posts for 404 page: {e}")
        recent_posts = []

    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context={
            "request": request,
            "current_user": current_user,
            "current_type": None,
            "canonical_url": f"{settings.BASE_URL}/404",
            "base_url": settings.BASE_URL,
            "recent_posts": recent_posts,
            "archive_sections": ARCHIVE_SECTIONS,
        },
        status_code=status.HTTP_404_NOT_FOUND,
    )


# --- Public Navigation & Content Routes ---

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    current_user = auth.get_current_user_optional(request)
    try:
        selected_posts = db.get_landing_selected_posts(limit=6)
        for p in selected_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))

        selected_slugs = [p["slug"] for p in selected_posts]
        recent_posts = db.get_recent_published_posts(limit=5, exclude_slugs=selected_slugs)
        for p in recent_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))
    except Exception as e:
        logger.error(f"Database error on home page: {e}")
        selected_posts = []
        recent_posts = []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_user": current_user,
        "current_type": None,
        "canonical_url": f"{settings.BASE_URL}/",
        "base_url": settings.BASE_URL,
        "selected_posts": selected_posts,
        "recent_posts": recent_posts,
        "archive_sections": ARCHIVE_SECTIONS
    })


@router.get("/about", response_class=HTMLResponse)
def about(request: Request):
    current_user = auth.get_current_user_optional(request)
    return templates.TemplateResponse("about.html", {
        "request": request,
        "current_user": current_user,
        "current_type": "about",
        "canonical_url": f"{settings.BASE_URL}/about",
        "base_url": settings.BASE_URL
    })


def _render_type_list(request: Request, post_type: str) -> HTMLResponse:
    current_user = auth.get_current_user_optional(request)
    meta = TYPE_METADATA.get(post_type, {"title": post_type.capitalize(), "description": ""})
    try:
        posts = db.get_published_posts(post_type=post_type, limit=50)
        for p in posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))
    except Exception as e:
        logger.error(f"Database error fetching {post_type}: {e}")
        posts = []

    return templates.TemplateResponse("list.html", {
        "request": request,
        "current_user": current_user,
        "current_type": post_type,
        "type_title": meta["title"],
        "type_description": meta["description"],
        "canonical_url": f"{settings.BASE_URL}/{post_type}",
        "base_url": settings.BASE_URL,
        "posts": posts
    })


@router.get("/writing", response_class=HTMLResponse)
def list_writing(request: Request):
    return _render_type_list(request, "writing")


@router.get("/research", response_class=HTMLResponse)
def list_research(request: Request):
    return _render_type_list(request, "research")


@router.get("/experiments", response_class=HTMLResponse)
def list_experiments(request: Request):
    return _render_type_list(request, "experiments")


@router.get("/projects", response_class=HTMLResponse)
def list_projects(request: Request):
    return _render_type_list(request, "projects")


@router.get("/books", response_class=HTMLResponse)
def list_books(request: Request):
    return _render_type_list(request, "books")


# --- SEO & Core System Routes ---

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    content = f"""User-agent: *
Allow: /
Disallow: /admin

Sitemap: {settings.BASE_URL}/sitemap.xml
"""
    return PlainTextResponse(content)


@router.get("/sitemap.xml")
def sitemap_xml(request: Request):
    try:
        posts = db.get_all_published_slugs()
    except Exception as e:
        logger.error(f"Error fetching posts for sitemap: {e}")
        posts = []

    try:
        courses = db.get_published_courses()
    except Exception as e:
        logger.error(f"Error fetching courses for sitemap: {e}")
        courses = []

    content = templates.get_template("sitemap.xml").render({
        "base_url": settings.BASE_URL,
        "posts": posts,
        "courses": courses
    })
    return Response(content=content, media_type="application/xml")


@router.post("/api/newsletter/subscribe")
async def subscribe_newsletter(data: NewsletterSignup):
    try:
        result = db.add_subscriber(str(data.email))
        is_new = result.get("created", False)
        return {
            "success": True,
            "status": "added" if is_new else "already_subscribed",
            "message": (
                f"Added {data.email}."
                if is_new
                else f"{data.email} is already on the list."
            )
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Newsletter subscription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process subscription right now."
        )


@router.get("/{post_type}/{slug}", response_class=HTMLResponse)
def post_detail(request: Request, post_type: str, slug: str):
    # If someone accesses /courses/{slug}, forward to course handler
    if post_type in ("courses", "course"):
        from .courses import course_detail
        return course_detail(request, slug)

    if post_type not in db.VALID_TYPES:
        return render_404(request)

    current_user = auth.get_current_user_optional(request)
    try:
        post = db.get_published_post_by_slug(post_type, slug)
    except Exception as e:
        logger.error(f"Database error fetching post {post_type}/{slug}: {e}")
        post = None

    if not post:
        return render_404(request)

    rendered_content, toc_content = markdown_utils.render_markdown_with_toc(post.get("content_markdown", ""))
    reading_time = markdown_utils.calculate_reading_time(post.get("content_markdown", ""))

    continue_reading = []
    if post.get("continue_reading_slugs"):
        try:
            continue_reading = db.get_continue_reading_posts(post["continue_reading_slugs"])
        except Exception as e:
            logger.error(f"Error fetching continue reading posts: {e}")

    canonical_url = f"{settings.BASE_URL}/{post_type}/{slug}"

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "current_user": current_user,
        "current_type": post_type,
        "post": post,
        "rendered_content": rendered_content,
        "toc_content": toc_content,
        "reading_time": reading_time,
        "continue_reading": continue_reading,
        "canonical_url": canonical_url,
        "base_url": settings.BASE_URL
    })
