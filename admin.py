import os
import logging
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

import db
import markdown_utils

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("made_for_nothing.admin")

ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", 8001))
PUBLIC_BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables and columns exist
    try:
        db.init_db()
        logger.info("Admin app initialized database schema.")
    except Exception as e:
        logger.error(f"Admin failed to initialize DB schema: {e}")
    yield


admin_app = FastAPI(
    title="MADE FOR NOTHING - Admin",
    description="Local-only administration application for MADE FOR NOTHING.",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)


# Security: Ensure requests originate strictly from localhost
@admin_app.middleware("http")
async def verify_localhost_only(request: Request, call_next):
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost", "testclient"):
        logger.warning(f"Rejected non-local access attempt to admin from {client_host}")
        return HTMLResponse(
            content="Forbidden: Admin is strictly accessible from localhost (127.0.0.1).",
            status_code=status.HTTP_403_FORBIDDEN
        )
    return await call_next(request)


# Mount Admin static assets and templates
admin_app.mount("/admin-static", StaticFiles(directory="admin/static"), name="admin-static")
templates = Jinja2Templates(directory="admin/templates")


@admin_app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    type: Optional[str] = None,
    status: Optional[str] = None,
    landing: Optional[str] = None,
    q: Optional[str] = None
):
    post_type = type if type in db.VALID_TYPES else None

    is_published = None
    if status == "published":
        is_published = True
    elif status == "draft":
        is_published = False

    show_on_landing = None
    if landing == "yes":
        show_on_landing = True
    elif landing == "no":
        show_on_landing = False

    try:
        posts = db.get_all_posts_admin(
            post_type=post_type,
            is_published=is_published,
            show_on_landing=show_on_landing,
            search=q
        )
        for p in posts:
            content = p.get("content_markdown", "") or ""
            words = len(content.split())
            p["word_count"] = words
            p["reading_time"] = markdown_utils.calculate_reading_time(content)
    except Exception as e:
        logger.error(f"Error fetching admin posts: {e}")
        posts = []

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "posts": posts,
        "valid_types": db.VALID_TYPES,
        "current_filter_type": post_type,
        "current_filter_status": status,
        "current_filter_landing": landing,
        "current_search": q,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.get("/posts/new", response_class=HTMLResponse)
def new_post_form(request: Request):
    try:
        available_posts = db.get_all_posts_for_selector()
    except Exception as e:
        logger.error(f"Error fetching selector posts: {e}")
        available_posts = []

    return templates.TemplateResponse("form.html", {
        "request": request,
        "post": None,
        "valid_types": db.VALID_TYPES,
        "available_posts": available_posts,
        "public_base_url": PUBLIC_BASE_URL,
        "error": None
    })


@admin_app.post("/posts/new", response_class=HTMLResponse)
async def create_post_action(request: Request):
    form_data = await request.form()

    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    post_type = form_data.get("type", "").strip()
    excerpt = form_data.get("excerpt", "").strip()
    content_markdown = form_data.get("content_markdown", "")
    is_published = form_data.get("is_published") is not None
    show_on_landing = form_data.get("show_on_landing") is not None
    tags_raw = form_data.get("tags", "")
    seo_title = form_data.get("seo_title", "").strip()
    seo_description = form_data.get("seo_description", "").strip()

    # Parse external links
    link_titles = form_data.getlist("link_title[]")
    link_urls = form_data.getlist("link_url[]")
    external_links = []
    for t, u in zip(link_titles, link_urls):
        t_clean = t.strip()
        u_clean = u.strip()
        if u_clean:
            external_links.append({"title": t_clean or u_clean, "url": u_clean})

    # Parse continue reading slugs (max 3)
    continue_reading_slugs = [s.strip() for s in form_data.getlist("continue_reading_slugs[]") if s.strip()][:3]

    data = {
        "title": title,
        "slug": slug,
        "type": post_type,
        "excerpt": excerpt,
        "content_markdown": content_markdown,
        "is_published": is_published,
        "show_on_landing": show_on_landing,
        "tags": tags_raw,
        "external_links": external_links,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "continue_reading_slugs": continue_reading_slugs
    }

    try:
        db.create_post(data)
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to create post: {e}")
        try:
            available_posts = db.get_all_posts_for_selector()
        except Exception:
            available_posts = []

        return templates.TemplateResponse("form.html", {
            "request": request,
            "post": data,
            "valid_types": db.VALID_TYPES,
            "available_posts": available_posts,
            "public_base_url": PUBLIC_BASE_URL,
            "error": f"Error saving post: {e}"
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.get("/posts/{post_id}/edit", response_class=HTMLResponse)
def edit_post_form(request: Request, post_id: int):
    post = db.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    try:
        available_posts = db.get_all_posts_for_selector(exclude_id=post_id)
    except Exception as e:
        logger.error(f"Error fetching selector posts: {e}")
        available_posts = []

    return templates.TemplateResponse("form.html", {
        "request": request,
        "post": post,
        "valid_types": db.VALID_TYPES,
        "available_posts": available_posts,
        "public_base_url": PUBLIC_BASE_URL,
        "error": None
    })


@admin_app.post("/posts/{post_id}/edit", response_class=HTMLResponse)
async def update_post_action(request: Request, post_id: int):
    form_data = await request.form()

    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    post_type = form_data.get("type", "").strip()
    excerpt = form_data.get("excerpt", "").strip()
    content_markdown = form_data.get("content_markdown", "")
    is_published = form_data.get("is_published") is not None
    show_on_landing = form_data.get("show_on_landing") is not None
    tags_raw = form_data.get("tags", "")
    seo_title = form_data.get("seo_title", "").strip()
    seo_description = form_data.get("seo_description", "").strip()

    # Parse external links
    link_titles = form_data.getlist("link_title[]")
    link_urls = form_data.getlist("link_url[]")
    external_links = []
    for t, u in zip(link_titles, link_urls):
        t_clean = t.strip()
        u_clean = u.strip()
        if u_clean:
            external_links.append({"title": t_clean or u_clean, "url": u_clean})

    # Parse continue reading slugs (max 3)
    continue_reading_slugs = [s.strip() for s in form_data.getlist("continue_reading_slugs[]") if s.strip()][:3]

    data = {
        "title": title,
        "slug": slug,
        "type": post_type,
        "excerpt": excerpt,
        "content_markdown": content_markdown,
        "is_published": is_published,
        "show_on_landing": show_on_landing,
        "tags": tags_raw,
        "external_links": external_links,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "continue_reading_slugs": continue_reading_slugs
    }

    try:
        db.update_post(post_id, data)
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to update post {post_id}: {e}")
        try:
            available_posts = db.get_all_posts_for_selector(exclude_id=post_id)
        except Exception:
            available_posts = []

        data["id"] = post_id
        return templates.TemplateResponse("form.html", {
            "request": request,
            "post": data,
            "valid_types": db.VALID_TYPES,
            "available_posts": available_posts,
            "public_base_url": PUBLIC_BASE_URL,
            "error": f"Error updating post: {e}"
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.post("/posts/{post_id}/toggle-publish")
def toggle_publish(post_id: int):
    try:
        db.toggle_publish_status(post_id)
    except Exception as e:
        logger.error(f"Error toggling publish for {post_id}: {e}")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/posts/{post_id}/toggle-landing")
def toggle_landing(post_id: int):
    try:
        db.toggle_landing_status(post_id)
    except Exception as e:
        logger.error(f"Error toggling landing status for {post_id}: {e}")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/posts/{post_id}/delete")
def delete_post_action(post_id: int):
    try:
        db.delete_post(post_id)
    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/api/preview")
async def preview_markdown(request: Request):
    try:
        payload = await request.json()
        md_text = payload.get("markdown", "")
    except Exception:
        md_text = ""

    html_content = markdown_utils.render_markdown(md_text)
    return JSONResponse(content={"html": html_content})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin:admin_app", host=ADMIN_HOST, port=ADMIN_PORT, reload=True)
