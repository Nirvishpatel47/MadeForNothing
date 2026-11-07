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
import mux_utils
import r2_storage
from routers.media import router as media_router

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


from core.security import SecurityHeadersMiddleware

admin_app = FastAPI(
    title="MADE FOR NOTHING - Admin",
    description="Local-only administration application for MADE FOR NOTHING.",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

# Apply Defensive Security Headers Middleware
admin_app.add_middleware(SecurityHeadersMiddleware)


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


# Mount Admin static assets and templates with reliable directory resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADMIN_STATIC_DIR = os.path.join(BASE_DIR, "admin", "static")
ADMIN_TEMPLATES_DIR = os.path.join(BASE_DIR, "admin", "templates")

admin_app.mount("/admin-static", StaticFiles(directory=ADMIN_STATIC_DIR if os.path.isdir(ADMIN_STATIC_DIR) else "admin/static"), name="admin-static")
templates = Jinja2Templates(directory=ADMIN_TEMPLATES_DIR if os.path.isdir(ADMIN_TEMPLATES_DIR) else "admin/templates")
admin_app.include_router(media_router)


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
        "admin_section": "posts",
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

    try:
        sections = db.get_all_sections_admin()
    except Exception as e:
        logger.error(f"Error fetching sections for new post: {e}")
        sections = []

    return templates.TemplateResponse("form.html", {
        "request": request,
        "post": None,
        "valid_types": db.VALID_TYPES,
        "available_posts": available_posts,
        "sections": sections,
        "selected_section_ids": [],
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

    # Parse assigned section IDs
    raw_section_ids = form_data.getlist("section_ids[]") + form_data.getlist("section_ids")
    section_ids = list(dict.fromkeys([int(s) for s in raw_section_ids if str(s).isdigit()]))

    # Featured image fields
    featured_image_alt = form_data.get("featured_image_alt", "").strip()
    featured_image_url = form_data.get("featured_image_url", "").strip() or None
    featured_image_key = form_data.get("featured_image_key", "").strip() or None
    featured_image_width = int(form_data.get("featured_image_width")) if form_data.get("featured_image_width") else None
    featured_image_height = int(form_data.get("featured_image_height")) if form_data.get("featured_image_height") else None
    featured_image_size = int(form_data.get("featured_image_size")) if form_data.get("featured_image_size") else None
    featured_image_mime = form_data.get("featured_image_mime", "").strip() or None
    featured_image_filename = form_data.get("featured_image_filename", "").strip() or None

    # Check if a file was uploaded directly via multipart form submission
    image_file = form_data.get("featured_image_file")
    if hasattr(image_file, "filename") and image_file.filename:
        try:
            file_bytes = await image_file.read()
            if file_bytes:
                upload_meta = r2_storage.upload_post_image(
                    file_bytes=file_bytes,
                    filename=image_file.filename,
                    post_type=post_type,
                    post_slug=slug
                )
                featured_image_url = upload_meta["url"]
                featured_image_key = upload_meta["key"]
                featured_image_width = upload_meta["width"]
                featured_image_height = upload_meta["height"]
                featured_image_size = upload_meta["size"]
                featured_image_mime = upload_meta["mime"]
                featured_image_filename = upload_meta["original_filename"]
        except Exception as img_err:
            logger.error(f"Error uploading image in create_post: {img_err}")
            try:
                available_posts = db.get_all_posts_for_selector()
            except Exception:
                available_posts = []
            return templates.TemplateResponse("form.html", {
                "request": request,
                "post": {
                    "title": title, "slug": slug, "type": post_type,
                    "excerpt": excerpt, "content_markdown": content_markdown,
                    "is_published": is_published, "show_on_landing": show_on_landing,
                    "tags": tags_raw, "external_links": external_links,
                    "seo_title": seo_title, "seo_description": seo_description,
                    "continue_reading_slugs": continue_reading_slugs,
                    "featured_image_alt": featured_image_alt,
                },
                "valid_types": db.VALID_TYPES,
                "available_posts": available_posts,
                "public_base_url": PUBLIC_BASE_URL,
                "error": f"Image Upload Error: {img_err}"
            }, status_code=status.HTTP_400_BAD_REQUEST)

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
        "continue_reading_slugs": continue_reading_slugs,
        "featured_image_url": featured_image_url,
        "featured_image_key": featured_image_key,
        "featured_image_alt": featured_image_alt or None,
        "featured_image_width": featured_image_width,
        "featured_image_height": featured_image_height,
        "featured_image_size": featured_image_size,
        "featured_image_mime": featured_image_mime,
        "featured_image_filename": featured_image_filename
    }

    try:
        new_post = db.create_post(data)
        if new_post and "id" in new_post and section_ids:
            try:
                db.set_post_sections(new_post["id"], section_ids)
            except Exception as sec_err:
                logger.error(f"Error setting sections for post {new_post['id']}: {sec_err}")
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to create post: {e}")
        try:
            available_posts = db.get_all_posts_for_selector()
        except Exception:
            available_posts = []
        try:
            sections = db.get_all_sections_admin()
        except Exception:
            sections = []

        return templates.TemplateResponse("form.html", {
            "request": request,
            "post": data,
            "valid_types": db.VALID_TYPES,
            "available_posts": available_posts,
            "sections": sections,
            "selected_section_ids": section_ids,
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

    try:
        sections = db.get_all_sections_admin()
        selected_section_ids = db.get_section_ids_for_post(post_id)
    except Exception as e:
        logger.error(f"Error fetching sections for post {post_id}: {e}")
        sections = []
        selected_section_ids = []

    return templates.TemplateResponse("form.html", {
        "request": request,
        "post": post,
        "valid_types": db.VALID_TYPES,
        "available_posts": available_posts,
        "sections": sections,
        "selected_section_ids": selected_section_ids,
        "public_base_url": PUBLIC_BASE_URL,
        "error": None
    })


@admin_app.post("/posts/{post_id}/edit", response_class=HTMLResponse)
async def update_post_action(request: Request, post_id: int):
    current_post = db.get_post_by_id(post_id)
    if not current_post:
        raise HTTPException(status_code=404, detail="Post not found")

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

    # Parse assigned section IDs
    raw_section_ids = form_data.getlist("section_ids[]") + form_data.getlist("section_ids")
    section_ids = list(dict.fromkeys([int(s) for s in raw_section_ids if str(s).isdigit()]))

    # Handle featured image removal or replacement
    remove_featured_image = form_data.get("remove_featured_image") in ("1", "true", "True")
    featured_image_alt = form_data.get("featured_image_alt", "").strip()
    featured_image_url = form_data.get("featured_image_url", "").strip() or None
    featured_image_key = form_data.get("featured_image_key", "").strip() or None
    featured_image_width = int(form_data.get("featured_image_width")) if form_data.get("featured_image_width") else None
    featured_image_height = int(form_data.get("featured_image_height")) if form_data.get("featured_image_height") else None
    featured_image_size = int(form_data.get("featured_image_size")) if form_data.get("featured_image_size") else None
    featured_image_mime = form_data.get("featured_image_mime", "").strip() or None
    featured_image_filename = form_data.get("featured_image_filename", "").strip() or None

    old_key = current_post.get("featured_image_key")

    # Check if a new file was uploaded directly in form
    image_file = form_data.get("featured_image_file")
    if hasattr(image_file, "filename") and image_file.filename:
        try:
            file_bytes = await image_file.read()
            if file_bytes:
                upload_meta = r2_storage.upload_post_image(
                    file_bytes=file_bytes,
                    filename=image_file.filename,
                    post_type=post_type,
                    post_slug=slug
                )
                featured_image_url = upload_meta["url"]
                featured_image_key = upload_meta["key"]
                featured_image_width = upload_meta["width"]
                featured_image_height = upload_meta["height"]
                featured_image_size = upload_meta["size"]
                featured_image_mime = upload_meta["mime"]
                featured_image_filename = upload_meta["original_filename"]
                # Clean up old key if replaced
                if old_key and old_key != featured_image_key:
                    r2_storage.delete_image_from_r2(old_key)
        except Exception as img_err:
            logger.error(f"Error uploading image in update_post: {img_err}")
            try:
                available_posts = db.get_all_posts_for_selector(exclude_id=post_id)
            except Exception:
                available_posts = []
            return templates.TemplateResponse("form.html", {
                "request": request,
                "post": {**current_post, "title": title, "slug": slug, "type": post_type, "excerpt": excerpt, "content_markdown": content_markdown},
                "valid_types": db.VALID_TYPES,
                "available_posts": available_posts,
                "public_base_url": PUBLIC_BASE_URL,
                "error": f"Image Upload Error: {img_err}"
            }, status_code=status.HTTP_400_BAD_REQUEST)
    elif remove_featured_image:
        if old_key:
            r2_storage.delete_image_from_r2(old_key)
        featured_image_url = None
        featured_image_key = None
        featured_image_alt = None
        featured_image_width = None
        featured_image_height = None
        featured_image_size = None
        featured_image_mime = None
        featured_image_filename = None
    elif featured_image_key and old_key and featured_image_key != old_key:
        # Replaced via AJAX upload
        r2_storage.delete_image_from_r2(old_key)

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
        "continue_reading_slugs": continue_reading_slugs,
        "remove_featured_image": remove_featured_image,
        "featured_image_url": featured_image_url,
        "featured_image_key": featured_image_key,
        "featured_image_alt": featured_image_alt or None,
        "featured_image_width": featured_image_width,
        "featured_image_height": featured_image_height,
        "featured_image_size": featured_image_size,
        "featured_image_mime": featured_image_mime,
        "featured_image_filename": featured_image_filename
    }

    try:
        db.update_post(post_id, data)
        try:
            db.set_post_sections(post_id, section_ids)
        except Exception as sec_err:
            logger.error(f"Error updating sections for post {post_id}: {sec_err}")
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Failed to update post {post_id}: {e}")
        try:
            available_posts = db.get_all_posts_for_selector(exclude_id=post_id)
        except Exception:
            available_posts = []
        try:
            sections = db.get_all_sections_admin()
        except Exception:
            sections = []

        data["id"] = post_id
        return templates.TemplateResponse("form.html", {
            "request": request,
            "post": data,
            "valid_types": db.VALID_TYPES,
            "available_posts": available_posts,
            "sections": sections,
            "selected_section_ids": section_ids,
            "public_base_url": PUBLIC_BASE_URL,
            "error": f"Error updating post: {e}"
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.post("/api/upload-image")
async def api_upload_image(request: Request):
    """
    Asynchronous image upload endpoint for the admin portal.
    Receives file, validates, converts to WebP, uploads to Cloudflare R2,
    and returns metadata.
    """
    try:
        form = await request.form()
        image_file = form.get("file")
        if not image_file or not hasattr(image_file, "filename") or not image_file.filename:
            return JSONResponse(
                {"success": False, "error": "No image file provided in upload request."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        post_type = form.get("type", "writing")
        post_slug = form.get("slug", "")

        file_bytes = await image_file.read()
        if not file_bytes:
            return JSONResponse(
                {"success": False, "error": "Uploaded image file is empty."},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        upload_meta = r2_storage.upload_post_image(
            file_bytes=file_bytes,
            filename=image_file.filename,
            post_type=post_type,
            post_slug=post_slug
        )

        return JSONResponse(upload_meta)
    except r2_storage.ImageValidationError as e:
        logger.warning(f"Admin image validation error: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=status.HTTP_400_BAD_REQUEST)
    except r2_storage.R2ConfigurationError as e:
        logger.error(f"Cloudflare R2 configuration error: {e}")
        return JSONResponse(
            {"success": False, "error": f"Cloudflare R2 is not configured: {e}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Unexpected image upload failure: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": f"Upload failed: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@admin_app.post("/api/delete-image")
async def api_delete_image(request: Request):
    """
    Endpoint to delete an uploaded image from Cloudflare R2 by key.
    """
    try:
        data = await request.json()
        key = data.get("key", "").strip()
        if not key:
            return JSONResponse({"success": False, "error": "Missing object key."}, status_code=status.HTTP_400_BAD_REQUEST)

        success = r2_storage.delete_image_from_r2(key)
        return JSONResponse({"success": success})
    except Exception as e:
        logger.error(f"Failed to delete image: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


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


# =============================================================================
# SECTION MANAGEMENT ROUTES
# =============================================================================

@admin_app.get("/sections", response_class=HTMLResponse)
def list_sections_admin(request: Request):
    try:
        sections = db.get_all_sections_admin()
    except Exception as e:
        logger.error(f"Error fetching sections for admin: {e}")
        sections = []

    return templates.TemplateResponse("sections_dashboard.html", {
        "request": request,
        "admin_section": "sections",
        "sections": sections,
        "valid_types": db.VALID_SECTION_TYPES,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.get("/sections/new", response_class=HTMLResponse)
def new_section_form(request: Request):
    return templates.TemplateResponse("section_form.html", {
        "request": request,
        "admin_section": "sections",
        "section": None,
        "valid_types": db.VALID_SECTION_TYPES,
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/sections/new", response_class=HTMLResponse)
async def create_section_action(request: Request):
    form_data = await request.form()
    name = form_data.get("name", "").strip()
    slug = form_data.get("slug", "").strip()
    description = form_data.get("description", "").strip()
    content_types = form_data.getlist("content_types[]") + form_data.getlist("content_types")
    content_types = list(dict.fromkeys([t.strip().lower() for t in content_types if t.strip()]))
    is_featured = form_data.get("is_featured") is not None
    is_published = form_data.get("is_published") is not None
    try:
        sort_order = int(form_data.get("sort_order", 0))
    except (ValueError, TypeError):
        sort_order = 0

    data = {
        "name": name,
        "slug": slug,
        "description": description,
        "content_types": content_types,
        "is_featured": is_featured,
        "is_published": is_published,
        "sort_order": sort_order,
    }

    try:
        db.create_section(data)
        return RedirectResponse(url="/sections", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error creating section: {e}")
        return templates.TemplateResponse("section_form.html", {
            "request": request,
            "admin_section": "sections",
            "section": data,
            "valid_types": db.VALID_SECTION_TYPES,
            "error": f"Failed to save section: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.get("/sections/{section_id}/edit", response_class=HTMLResponse)
def edit_section_form(request: Request, section_id: int):
    section = db.get_section_by_id(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    return templates.TemplateResponse("section_form.html", {
        "request": request,
        "admin_section": "sections",
        "section": section,
        "valid_types": db.VALID_SECTION_TYPES,
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/sections/{section_id}/edit", response_class=HTMLResponse)
async def update_section_action(request: Request, section_id: int):
    section = db.get_section_by_id(section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    form_data = await request.form()
    name = form_data.get("name", "").strip()
    slug = form_data.get("slug", "").strip()
    description = form_data.get("description", "").strip()
    content_types = form_data.getlist("content_types[]") + form_data.getlist("content_types")
    content_types = list(dict.fromkeys([t.strip().lower() for t in content_types if t.strip()]))
    is_featured = form_data.get("is_featured") is not None
    is_published = form_data.get("is_published") is not None
    try:
        sort_order = int(form_data.get("sort_order", 0))
    except (ValueError, TypeError):
        sort_order = 0

    data = {
        "name": name,
        "slug": slug,
        "description": description,
        "content_types": content_types,
        "is_featured": is_featured,
        "is_published": is_published,
        "sort_order": sort_order,
    }

    try:
        db.update_section(section_id, data)
        return RedirectResponse(url="/sections", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error updating section: {e}")
        return templates.TemplateResponse("section_form.html", {
            "request": request,
            "admin_section": "sections",
            "section": {**section, **data},
            "valid_types": db.VALID_SECTION_TYPES,
            "error": f"Failed to update section: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.post("/sections/{section_id}/toggle-publish")
def toggle_section_publish_action(section_id: int):
    try:
        db.toggle_section_publish(section_id)
    except Exception as e:
        logger.error(f"Error toggling section publish {section_id}: {e}")
    return RedirectResponse(url="/sections", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/sections/{section_id}/delete")
def delete_section_action(section_id: int):
    try:
        db.delete_section(section_id)
    except Exception as e:
        logger.error(f"Error deleting section {section_id}: {e}")
    return RedirectResponse(url="/sections", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/sections/reorder")
async def reorder_sections_action(request: Request):
    try:
        body = await request.json()
        ordered_ids = body.get("ordered_ids", [])
        if ordered_ids:
            clean_ids = [int(x) for x in ordered_ids if str(x).isdigit()]
            db.reorder_sections(clean_ids)
        return JSONResponse(content={"success": True})
    except Exception as e:
        logger.error(f"Error reordering sections: {e}")
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# =============================================================================
# COURSE MANAGEMENT ROUTES
# =============================================================================

@admin_app.get("/courses", response_class=HTMLResponse)
@admin_app.get("/courses/dashboard", response_class=HTMLResponse)
def list_courses_admin(request: Request):
    try:
        courses = db.get_all_courses_admin()
    except Exception as e:
        logger.error(f"Error fetching admin courses: {e}")
        courses = []

    return templates.TemplateResponse("courses_dashboard.html", {
        "request": request,
        "admin_section": "courses",
        "courses": courses,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.get("/courses/new", response_class=HTMLResponse)
def new_course_form(request: Request):
    try:
        sections = db.get_all_sections_admin()
    except Exception as e:
        logger.error(f"Error fetching sections for new course: {e}")
        sections = []

    return templates.TemplateResponse("course_form.html", {
        "request": request,
        "admin_section": "courses",
        "course": None,
        "sections": sections,
        "selected_section_ids": [],
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/courses/new", response_class=HTMLResponse)
async def create_course_action(request: Request):
    form_data = await request.form()
    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    subtitle = form_data.get("subtitle", "").strip()
    description = form_data.get("description", "").strip()
    what_you_will_learn = form_data.get("what_you_will_learn", "").strip()
    target_audience = form_data.get("target_audience", "").strip()
    instructor_bio = form_data.get("instructor_bio", "").strip()
    price_raw = form_data.get("price", "0").strip()
    thumbnail = form_data.get("thumbnail", "").strip()
    is_published = form_data.get("is_published") is not None

    try:
        price = max(0, int(price_raw))
    except ValueError:
        price = 0

    # Parse FAQs
    faq_questions = form_data.getlist("faq_question[]")
    faq_answers = form_data.getlist("faq_answer[]")
    faq = []
    for q, a in zip(faq_questions, faq_answers):
        if q.strip() and a.strip():
            faq.append({"question": q.strip(), "answer": a.strip()})

    raw_section_ids = form_data.getlist("section_ids[]") + form_data.getlist("section_ids")
    section_ids = list(dict.fromkeys([int(s) for s in raw_section_ids if str(s).isdigit()]))

    data = {
        "title": title,
        "slug": slug,
        "subtitle": subtitle,
        "description": description,
        "what_you_will_learn": what_you_will_learn,
        "target_audience": target_audience,
        "instructor_bio": instructor_bio,
        "price": price,
        "thumbnail": thumbnail,
        "is_published": is_published,
        "faq": faq
    }

    try:
        new_course = db.create_course(data)
        if new_course and "id" in new_course and section_ids:
            try:
                db.set_course_sections(new_course["id"], section_ids)
            except Exception as sec_err:
                logger.error(f"Error setting sections for course {new_course['id']}: {sec_err}")
        return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error creating course: {e}")
        try:
            sections = db.get_all_sections_admin()
        except Exception:
            sections = []
        return templates.TemplateResponse("course_form.html", {
            "request": request,
            "admin_section": "courses",
            "course": data,
            "sections": sections,
            "selected_section_ids": section_ids,
            "error": f"Failed to save course: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.get("/courses/{course_id}/edit", response_class=HTMLResponse)
def edit_course_form(request: Request, course_id: int):
    course = db.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        sections = db.get_all_sections_admin()
        selected_section_ids = db.get_section_ids_for_course(course_id)
    except Exception as e:
        logger.error(f"Error fetching sections for course {course_id}: {e}")
        sections = []
        selected_section_ids = []

    return templates.TemplateResponse("course_form.html", {
        "request": request,
        "admin_section": "courses",
        "course": course,
        "sections": sections,
        "selected_section_ids": selected_section_ids,
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/courses/{course_id}/edit", response_class=HTMLResponse)
async def update_course_action(request: Request, course_id: int):
    form_data = await request.form()
    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    subtitle = form_data.get("subtitle", "").strip()
    description = form_data.get("description", "").strip()
    what_you_will_learn = form_data.get("what_you_will_learn", "").strip()
    target_audience = form_data.get("target_audience", "").strip()
    instructor_bio = form_data.get("instructor_bio", "").strip()
    price_raw = form_data.get("price", "0").strip()
    thumbnail = form_data.get("thumbnail", "").strip()
    is_published = form_data.get("is_published") is not None

    try:
        price = max(0, int(price_raw))
    except ValueError:
        price = 0

    faq_questions = form_data.getlist("faq_question[]")
    faq_answers = form_data.getlist("faq_answer[]")
    faq = []
    for q, a in zip(faq_questions, faq_answers):
        if q.strip() and a.strip():
            faq.append({"question": q.strip(), "answer": a.strip()})

    raw_section_ids = form_data.getlist("section_ids[]") + form_data.getlist("section_ids")
    section_ids = list(dict.fromkeys([int(s) for s in raw_section_ids if str(s).isdigit()]))

    data = {
        "title": title,
        "slug": slug,
        "subtitle": subtitle,
        "description": description,
        "what_you_will_learn": what_you_will_learn,
        "target_audience": target_audience,
        "instructor_bio": instructor_bio,
        "price": price,
        "thumbnail": thumbnail,
        "is_published": is_published,
        "faq": faq
    }

    try:
        db.update_course(course_id, data)
        try:
            db.set_course_sections(course_id, section_ids)
        except Exception as sec_err:
            logger.error(f"Error updating sections for course {course_id}: {sec_err}")
        return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error updating course {course_id}: {e}")
        try:
            sections = db.get_all_sections_admin()
        except Exception:
            sections = []
        data["id"] = course_id
        return templates.TemplateResponse("course_form.html", {
            "request": request,
            "admin_section": "courses",
            "course": data,
            "sections": sections,
            "selected_section_ids": section_ids,
            "error": f"Failed to update course: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.post("/courses/{course_id}/toggle-publish")
def toggle_course_publish(course_id: int):
    try:
        db.toggle_course_publish_status(course_id)
    except Exception as e:
        logger.error(f"Error toggling course publish {course_id}: {e}")
    return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/courses/{course_id}/delete")
def delete_course_action(course_id: int):
    try:
        db.delete_course(course_id)
    except Exception as e:
        logger.error(f"Error deleting course {course_id}: {e}")
    return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)


# =============================================================================
# LESSON MANAGEMENT ROUTES
# =============================================================================

@admin_app.get("/courses/{course_id}/lessons", response_class=HTMLResponse)
def list_lessons_admin(request: Request, course_id: int):
    course = db.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = db.get_all_lessons_admin(course_id)
    return templates.TemplateResponse("course_lessons.html", {
        "request": request,
        "admin_section": "courses",
        "course": course,
        "lessons": lessons,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.get("/courses/{course_id}/lessons/new", response_class=HTMLResponse)
def new_lesson_form(request: Request, course_id: int):
    course = db.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    existing_lessons = db.get_all_lessons_admin(course_id)
    default_order = len(existing_lessons) + 1

    return templates.TemplateResponse("lesson_form.html", {
        "request": request,
        "admin_section": "courses",
        "course": course,
        "lesson": None,
        "default_order": default_order,
        "questions": [],
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/courses/{course_id}/lessons/new", response_class=HTMLResponse)
async def create_lesson_action(request: Request, course_id: int):
    course = db.get_course_by_id(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    form_data = await request.form()
    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    order_index = int(form_data.get("order_index", "1") or "1")
    description = form_data.get("description", "").strip()
    content_markdown = form_data.get("content_markdown", "")
    mux_asset_id = form_data.get("mux_asset_id", "").strip()
    mux_playback_id = form_data.get("mux_playback_id", "").strip()
    mux_upload_id = form_data.get("mux_upload_id", "").strip()
    mux_status = form_data.get("mux_status", "none").strip()
    duration_seconds = int(form_data.get("duration_seconds", "0") or "0")
    is_published = form_data.get("is_published") is not None

    data = {
        "course_id": course_id,
        "title": title,
        "slug": slug,
        "order_index": order_index,
        "description": description,
        "content_markdown": content_markdown,
        "mux_asset_id": mux_asset_id,
        "mux_playback_id": mux_playback_id,
        "mux_upload_id": mux_upload_id,
        "mux_status": mux_status,
        "duration_seconds": duration_seconds,
        "is_published": is_published
    }

    try:
        created = db.create_lesson(data)
        return RedirectResponse(url=f"/lessons/{created['id']}/edit", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error creating lesson: {e}")
        return templates.TemplateResponse("lesson_form.html", {
            "request": request,
            "admin_section": "courses",
            "course": course,
            "lesson": data,
            "default_order": order_index,
            "questions": [],
            "error": f"Failed to create lesson: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.get("/lessons/{lesson_id}/edit", response_class=HTMLResponse)
def edit_lesson_form(request: Request, lesson_id: int):
    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    course = db.get_course_by_id(lesson["course_id"])
    questions = db.get_questions_by_lesson(lesson_id)
    student_responses = db.get_student_responses_for_lesson_admin(lesson_id)
    responses_by_question = {}
    for r in student_responses:
        qid = r["question_id"]
        if qid not in responses_by_question:
            responses_by_question[qid] = []
        responses_by_question[qid].append(r)

    return templates.TemplateResponse("lesson_form.html", {
        "request": request,
        "admin_section": "courses",
        "course": course,
        "lesson": lesson,
        "questions": questions,
        "responses_by_question": responses_by_question,
        "error": None,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/lessons/{lesson_id}/edit", response_class=HTMLResponse)
async def update_lesson_action(request: Request, lesson_id: int):
    lesson = db.get_lesson_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    course = db.get_course_by_id(lesson["course_id"])
    form_data = await request.form()

    title = form_data.get("title", "").strip()
    slug = form_data.get("slug", "").strip()
    order_index = int(form_data.get("order_index", "1") or "1")
    description = form_data.get("description", "").strip()
    content_markdown = form_data.get("content_markdown", "")
    mux_asset_id = form_data.get("mux_asset_id", "").strip()
    mux_playback_id = form_data.get("mux_playback_id", "").strip()
    mux_upload_id = form_data.get("mux_upload_id", "").strip()
    mux_status = form_data.get("mux_status", "none").strip()
    duration_seconds = int(form_data.get("duration_seconds", "0") or "0")
    is_published = form_data.get("is_published") is not None

    data = {
        "title": title,
        "slug": slug,
        "order_index": order_index,
        "description": description,
        "content_markdown": content_markdown,
        "mux_asset_id": mux_asset_id,
        "mux_playback_id": mux_playback_id,
        "mux_upload_id": mux_upload_id,
        "mux_status": mux_status,
        "duration_seconds": duration_seconds,
        "is_published": is_published
    }

    try:
        db.update_lesson(lesson_id, data)
        return RedirectResponse(url=f"/courses/{course['id']}/lessons", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error updating lesson {lesson_id}: {e}")
        data["id"] = lesson_id
        questions = db.get_questions_by_lesson(lesson_id)
        return templates.TemplateResponse("lesson_form.html", {
            "request": request,
            "admin_section": "courses",
            "course": course,
            "lesson": data,
            "questions": questions,
            "error": f"Failed to update lesson: {e}",
            "public_base_url": PUBLIC_BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)


@admin_app.post("/lessons/{lesson_id}/delete")
def delete_lesson_action(lesson_id: int):
    lesson = db.get_lesson_by_id(lesson_id)
    if lesson:
        course_id = lesson["course_id"]
        db.delete_lesson(lesson_id)
        return RedirectResponse(url=f"/courses/{course_id}/lessons", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)


# =============================================================================
# QUESTION & ANSWER ROUTES (Q&A)
# =============================================================================

@admin_app.post("/lessons/{lesson_id}/questions/new")
async def add_question_action(request: Request, lesson_id: int):
    form_data = await request.form()
    question = form_data.get("question", "").strip()
    answer = form_data.get("answer", "").strip()
    sort_order = int(form_data.get("sort_order", "0") or "0")

    if question and answer:
        try:
            db.create_question(lesson_id, question, answer, sort_order)
        except Exception as e:
            logger.error(f"Error adding question to lesson {lesson_id}: {e}")

    return RedirectResponse(url=f"/lessons/{lesson_id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/questions/{question_id}/delete")
def delete_question_action(question_id: int):
    try:
        deleted = db.delete_question(question_id)
        if deleted and deleted.get("lesson_id"):
            return RedirectResponse(url=f"/lessons/{deleted['lesson_id']}/edit", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        logger.error(f"Error deleting question {question_id}: {e}")

    return RedirectResponse(url="/courses", status_code=status.HTTP_303_SEE_OTHER)


# =============================================================================
# MUX DIRECT UPLOADS & STATUS APIS (ADMIN)
# =============================================================================

@admin_app.post("/admin/api/mux/uploads")
def api_create_mux_direct_upload():
    """Initializes direct upload with Mux API configuring signed playback."""
    result = mux_utils.create_direct_upload()
    return JSONResponse(content=result)


@admin_app.get("/admin/api/mux/status/{upload_id}")
def api_check_mux_status(upload_id: str):
    """Polls Mux upload and asset status."""
    result = mux_utils.check_upload_status(upload_id)
    return JSONResponse(content=result)


# =============================================================================
# PAYMENT VERIFICATION & ORDERS ROUTES
# =============================================================================

@admin_app.get("/payments", response_class=HTMLResponse)
def list_payments_admin(request: Request, status: Optional[str] = "all"):
    filter_status = status if status in ("pending", "approved", "rejected") else None
    payments = db.get_payment_submissions_admin(status=filter_status)

    all_payments = db.get_payment_submissions_admin()
    pending_count = sum(1 for p in all_payments if p["status"] == "pending")
    approved_count = sum(1 for p in all_payments if p["status"] == "approved")
    rejected_count = sum(1 for p in all_payments if p["status"] == "rejected")
    all_count = len(all_payments)

    return templates.TemplateResponse("payments_dashboard.html", {
        "request": request,
        "admin_section": "payments",
        "payments": payments,
        "current_status": status,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "all_count": all_count,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/payments/{payment_id}/approve")
def approve_payment_action(payment_id: int):
    try:
        db.approve_payment_submission(payment_id, reviewed_by="Admin")
    except Exception as e:
        logger.error(f"Error approving payment {payment_id}: {e}")
    return RedirectResponse(url="/payments", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/payments/{payment_id}/reject")
def reject_payment_action(payment_id: int):
    try:
        db.reject_payment_submission(payment_id, reviewed_by="Admin")
    except Exception as e:
        logger.error(f"Error rejecting payment {payment_id}: {e}")
    return RedirectResponse(url="/payments", status_code=status.HTTP_303_SEE_OTHER)


# =============================================================================
# STUDENT ENROLLMENTS ROUTES
# =============================================================================

@admin_app.get("/students", response_class=HTMLResponse)
def list_students_admin(request: Request):
    try:
        enrollments = db.get_all_enrollments_admin()
    except Exception as e:
        logger.error(f"Error fetching enrollments: {e}")
        enrollments = []

    return templates.TemplateResponse("students_dashboard.html", {
        "request": request,
        "admin_section": "students",
        "enrollments": enrollments,
        "public_base_url": PUBLIC_BASE_URL
    })


@admin_app.post("/students/{user_id}/courses/{course_id}/grant")
def grant_student_access_action(user_id: int, course_id: int):
    try:
        db.create_or_update_enrollment(user_id, course_id, status="active")
    except Exception as e:
        logger.error(f"Error granting access to user {user_id}, course {course_id}: {e}")
    return RedirectResponse(url="/students", status_code=status.HTTP_303_SEE_OTHER)


@admin_app.post("/students/{user_id}/courses/{course_id}/revoke")
def revoke_student_access_action(user_id: int, course_id: int):
    try:
        db.revoke_enrollment(user_id, course_id)
    except Exception as e:
        logger.error(f"Error revoking access for user {user_id}, course {course_id}: {e}")
    return RedirectResponse(url="/students", status_code=status.HTTP_303_SEE_OTHER)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("admin:admin_app", host=ADMIN_HOST, port=ADMIN_PORT, reload=True)
