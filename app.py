import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

import db
import markdown_utils

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("made_for_nothing.public")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
PUBLIC_HOST = os.getenv("PUBLIC_HOST", "0.0.0.0")
PUBLIC_PORT = int(os.getenv("PUBLIC_PORT", 8000))

TYPE_METADATA = {
    "writing": {
        "title": "Writing",
        "description": "Longform essays, philosophical inquiries, and reflections on design, systems, and craft."
    },
    "research": {
        "title": "Research",
        "description": "Structured investigations, deep dives, literature notes, and theoretical models."
    },
    "experiments": {
        "title": "Experiments",
        "description": "Technical tests, code prototypes, architectural explorations, and benchmarks."
    },
    "projects": {
        "title": "Projects",
        "description": "Finished artifacts, open tools, focused software libraries, and public works."
    },
    "books": {
        "title": "Books",
        "description": "Reading notes, marginalia, thematic analyses, and annotated literature."
    }
}

ARCHIVE_SECTIONS = [
    {"type": "writing", "title": "Writing", "desc": "Longform essays, philosophical inquiries, and reflections."},
    {"type": "research", "title": "Research", "desc": "Structured investigations, theoretical models, and notes."},
    {"type": "experiments", "title": "Experiments", "desc": "Technical prototypes, benchmark tests, and code explorations."},
    {"type": "projects", "title": "Projects", "desc": "Finished tools, open source software, and public artifacts."},
    {"type": "books", "title": "Books", "desc": "Marginalia, reading notes, and conceptual summaries."}
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema safely
    try:
        db.init_db()
        logger.info("Public app initialized database connection and schema successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")
    yield


app = FastAPI(
    title="MADE FOR NOTHING",
    description="A personal research archive of writing, research, experiments, projects, and books.",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan
)

# Static and Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# --- SEO & Core System Routes ---

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    content = f"""User-agent: *
Allow: /
Disallow: /admin

Sitemap: {BASE_URL}/sitemap.xml
"""
    return PlainTextResponse(content)


@app.get("/sitemap.xml")
def sitemap_xml(request: Request):
    try:
        posts = db.get_all_published_slugs()
    except Exception as e:
        logger.error(f"Error fetching posts for sitemap: {e}")
        posts = []

    content = templates.get_template("sitemap.xml").render({
        "base_url": BASE_URL,
        "posts": posts
    })
    return Response(content=content, media_type="application/xml")


# --- Public Navigation & Content Routes ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    try:
        # Strictly fetch curated items with show_on_landing = TRUE
        selected_posts = db.get_landing_selected_posts(limit=6)
        for p in selected_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))

        selected_slugs = [p["slug"] for p in selected_posts]

        # Recent published items
        recent_posts = db.get_recent_published_posts(limit=5, exclude_slugs=selected_slugs)
        for p in recent_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))
    except Exception as e:
        logger.error(f"Database error on home page: {e}")
        selected_posts = []
        recent_posts = []

    return templates.TemplateResponse("index.html", {
        "request": request,
        "current_type": None,
        "canonical_url": f"{BASE_URL}/",
        "base_url": BASE_URL,
        "selected_posts": selected_posts,
        "recent_posts": recent_posts,
        "archive_sections": ARCHIVE_SECTIONS
    })


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return templates.TemplateResponse("about.html", {
        "request": request,
        "current_type": "about",
        "canonical_url": f"{BASE_URL}/about",
        "base_url": BASE_URL
    })


@app.get("/writing", response_class=HTMLResponse)
def list_writing(request: Request):
    return _render_type_list(request, "writing")


@app.get("/research", response_class=HTMLResponse)
def list_research(request: Request):
    return _render_type_list(request, "research")


@app.get("/experiments", response_class=HTMLResponse)
def list_experiments(request: Request):
    return _render_type_list(request, "experiments")


@app.get("/projects", response_class=HTMLResponse)
def list_projects(request: Request):
    return _render_type_list(request, "projects")


@app.get("/books", response_class=HTMLResponse)
def list_books(request: Request):
    return _render_type_list(request, "books")


def _render_type_list(request: Request, post_type: str):
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
        "current_type": post_type,
        "type_title": meta["title"],
        "type_description": meta["description"],
        "canonical_url": f"{BASE_URL}/{post_type}",
        "base_url": BASE_URL,
        "posts": posts
    })


@app.get("/{post_type}/{slug}", response_class=HTMLResponse)
def post_detail(request: Request, post_type: str, slug: str):
    if post_type not in db.VALID_TYPES:
        return _render_404(request)

    try:
        post = db.get_published_post_by_slug(post_type, slug)
    except Exception as e:
        logger.error(f"Database error fetching post {post_type}/{slug}: {e}")
        post = None

    if not post:
        return _render_404(request)

    rendered_content, toc_content = markdown_utils.render_markdown_with_toc(post.get("content_markdown", ""))
    reading_time = markdown_utils.calculate_reading_time(post.get("content_markdown", ""))

    continue_reading = []
    if post.get("continue_reading_slugs"):
        try:
            continue_reading = db.get_continue_reading_posts(post["continue_reading_slugs"])
        except Exception as e:
            logger.error(f"Error fetching continue reading posts: {e}")

    canonical_url = f"{BASE_URL}/{post_type}/{slug}"

    return templates.TemplateResponse("detail.html", {
        "request": request,
        "current_type": post_type,
        "post": post,
        "rendered_content": rendered_content,
        "toc_content": toc_content,
        "reading_time": reading_time,
        "continue_reading": continue_reading,
        "canonical_url": canonical_url,
        "base_url": BASE_URL
    })


def _render_404(request: Request):
    try:
        recent_posts = db.get_recent_published_posts(limit=4)
        for p in recent_posts:
            p["reading_time"] = markdown_utils.calculate_reading_time(p.get("content_markdown", ""))
    except Exception:
        recent_posts = []

    return templates.TemplateResponse("404.html", {
        "request": request,
        "current_type": None,
        "canonical_url": f"{BASE_URL}/404",
        "base_url": BASE_URL,
        "recent_posts": recent_posts,
        "archive_sections": ARCHIVE_SECTIONS
    }, status_code=404)


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return _render_404(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=PUBLIC_HOST, port=PUBLIC_PORT, reload=True)
