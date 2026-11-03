"""
MADE FOR NOTHING — Public Application Entrypoint
A research archive and digital studio platform exploring distributed systems,
durable software architecture, theoretical computing, and philosophy.
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
from core.config import settings
from core.security import SecurityHeadersMiddleware
from routers import (
    courses_router,
    payments_router,
    lessons_router,
    auth_router,
    public_router,
)
from routers.public import render_404

# Configure structured application logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("made_for_nothing.public")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for clean startup and shutdown."""
    try:
        db.init_db()
        logger.info("Database schema and foreign key constraints verified successfully.")
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

# Apply Defensive Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Mount Static Assets & Templates
app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


# --- Global Exception Handlers ---

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return render_404(request)


@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    # Editorial 500 error page without leaking stack traces or credentials
    current_user = None
    try:
        import auth
        current_user = auth.get_current_user_optional(request)
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context={
            "request": request,
            "current_user": current_user,
            "current_type": None,
            "canonical_url": f"{settings.BASE_URL}/500",
            "base_url": settings.BASE_URL,
            "recent_posts": [],
            "archive_sections": [],
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# --- Include Modular Domain Routers ---
# Note: Course and Payment routers are registered before Public to ensure specific routes take precedence
app.include_router(courses_router)
app.include_router(payments_router)
app.include_router(lessons_router)
app.include_router(auth_router)
app.include_router(public_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host=settings.PUBLIC_HOST, port=settings.PUBLIC_PORT, reload=True)