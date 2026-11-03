"""
Centralized Configuration & Settings for MADE FOR NOTHING.
Loads environment variables safely and provides structured constants.
"""
import os
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Settings:
    # Directory paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TEMPLATES_DIR: str = os.path.join(BASE_DIR, "templates") if os.path.isdir(os.path.join(BASE_DIR, "templates")) else "templates"
    STATIC_DIR: str = os.path.join(BASE_DIR, "static") if os.path.isdir(os.path.join(BASE_DIR, "static")) else "static"

    # Environment & Base URLs
    ENV: str = os.getenv("ENV", "development").lower()
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    PUBLIC_HOST: str = os.getenv("PUBLIC_HOST", "0.0.0.0")
    PUBLIC_PORT: int = int(os.getenv("PUBLIC_PORT", "8000"))

    # Admin Portal (strictly local security)
    ADMIN_HOST: str = os.getenv("ADMIN_HOST", "127.0.0.1")
    ADMIN_PORT: int = int(os.getenv("ADMIN_PORT", "8001"))

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Payment Settings (Direct UPI settlement)
    COURSE_UPI_ID: str = os.getenv("COURSE_UPI_ID", "madefornothing@upi")
    COURSE_PAYMENT_NAME: str = os.getenv("COURSE_PAYMENT_NAME", "MADE FOR NOTHING")

    # Session & JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "mfn-default-jwt-secret-key-change-in-production-32chars")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))
    COOKIE_NAME: str = "__session"
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() in ("true", "1", "yes") or BASE_URL.startswith("https://")

    # Firebase Authentication
    FIREBASE_API_KEY: str = os.getenv("FIREBASE_API_KEY", "").strip()
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    FIREBASE_AUTH_DOMAIN: str = os.getenv("FIREBASE_AUTH_DOMAIN", "").strip()
    FIREBASE_REQUIRE_EMAIL_VERIFICATION: bool = (
        os.getenv("FIREBASE_REQUIRE_EMAIL_VERIFICATION", "true").strip().lower() in ("true", "1", "yes")
    )

    # Mux Video API
    MUX_TOKEN_ID: str = os.getenv("MUX_TOKEN_ID", "").strip()
    MUX_TOKEN_SECRET: str = os.getenv("MUX_TOKEN_SECRET", "").strip()
    MUX_SIGNING_KEY_ID: str = os.getenv("MUX_SIGNING_KEY_ID", "").strip()
    MUX_SIGNING_PRIVATE_KEY: str = os.getenv("MUX_SIGNING_PRIVATE_KEY", "").strip()


settings = Settings()

# Post types metadata
TYPE_METADATA: Dict[str, Dict[str, str]] = {
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

# Archive sections for navigation
ARCHIVE_SECTIONS: List[Dict[str, str]] = [
    {"type": "writing", "title": "Writing", "desc": "Longform essays, philosophical inquiries, and reflections."},
    {"type": "research", "title": "Research", "desc": "Structured investigations, theoretical models, and notes."},
    {"type": "experiments", "title": "Experiments", "desc": "Technical prototypes, benchmark tests, and code explorations."},
    {"type": "projects", "title": "Projects", "desc": "Finished tools, open source software, and public artifacts."},
    {"type": "books", "title": "Books", "desc": "Marginalia, reading notes, and conceptual summaries."}
]
