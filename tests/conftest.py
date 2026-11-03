"""
Pytest configuration and shared test fixtures for MADE FOR NOTHING.
Configures test environments, mock dependencies, and test clients.
"""
import os
import sys
from typing import Generator
import pytest
from starlette.testclient import TestClient

# Ensure Website directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set test environment variables
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-characters-long-for-testing")
os.environ.setdefault("BASE_URL", "http://testserver")
os.environ.setdefault("ADMIN_HOST", "127.0.0.1")
os.environ.setdefault("ADMIN_PORT", "8001")
os.environ.setdefault("COURSE_UPI_ID", "test@upi")
os.environ.setdefault("COURSE_PAYMENT_NAME", "TEST COURSE")

from app import app
from admin import admin_app
import auth


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Test client for public application."""
    with TestClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def admin_client() -> Generator[TestClient, None, None]:
    """Test client for localhost-only admin application."""
    with TestClient(admin_app, base_url="http://127.0.0.1:8001") as c:
        yield c


@pytest.fixture
def mock_user():
    """Returns a sample enrolled user dict."""
    return {
        "id": 42,
        "email": "student@example.com",
        "name": "Alex Student",
        "mobile_number": "9876543210",
        "firebase_uid": "fb_uid_test_42",
        "email_verified": True,
        "is_active": True
    }


@pytest.fixture
def auth_cookie(mock_user):
    """Generates a valid JWT session cookie string for mock_user."""
    token = auth.create_access_token(
        user_id=mock_user["id"],
        email=mock_user["email"],
        firebase_uid=mock_user["firebase_uid"]
    )
    return token


@pytest.fixture
def authenticated_client(client, auth_cookie) -> TestClient:
    """Returns a client with an authenticated session cookie pre-set."""
    client.cookies.set(auth.COOKIE_NAME, auth_cookie)
    return client


@pytest.fixture
def sample_course():
    """Returns a sample published course dict."""
    return {
        "id": 1,
        "title": "Systems Architecture & Durable Software",
        "slug": "systems-architecture",
        "subtitle": "Engineering resilient platforms",
        "description": "Comprehensive course on distributed architectures.",
        "what_you_will_learn": "Distributed consensus, storage engines, durability.",
        "target_audience": "Software architects and senior engineers.",
        "price": 4999,
        "thumbnail": "/static/images/logo.png",
        "is_published": True,
        "faq": [],
        "instructor_bio": "Independent systems researcher."
    }


@pytest.fixture
def sample_lesson():
    """Returns a sample published lesson dict."""
    return {
        "id": 101,
        "course_id": 1,
        "course_slug": "systems-architecture",
        "title": "Storage Engine Internals: LSM Trees & WAL",
        "slug": "storage-engine-internals",
        "order_index": 1,
        "description": "Deep dive into write-ahead logging and log-structured merge trees.",
        "content_markdown": "# Storage Engine Internals\n\nLog structured merge trees maximize sequential write throughput.",
        "mux_playback_id": "test_playback_id_123",
        "mux_status": "ready",
        "duration_seconds": 1800,
        "is_published": True
    }
