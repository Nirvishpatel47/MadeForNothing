"""
Integration tests for Article Featured Image Management across Admin Portal and Public Website.
"""
import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

import db
import r2_storage
from core.config import settings


def make_dummy_jpeg() -> bytes:
    img = Image.new("RGB", (300, 200), color=(80, 120, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_admin_api_upload_image_success(admin_client):
    """Admin upload endpoint accepts valid image, optimizes to WebP, and returns metadata."""
    raw_img = make_dummy_jpeg()
    mock_meta = {
        "success": True,
        "url": "https://pub-r2.dev/images/writing/2026/11/abc_test.webp",
        "key": "images/writing/2026/11/abc_test.webp",
        "width": 300,
        "height": 200,
        "size": 1500,
        "mime": "image/webp",
        "original_filename": "cover.jpg"
    }

    with patch("r2_storage.upload_post_image", return_value=mock_meta):
        files = {"file": ("cover.jpg", raw_img, "image/jpeg")}
        data = {"type": "writing", "slug": "test-article"}
        resp = admin_client.post("/api/upload-image", data=data, files=files)

        assert resp.status_code == 200
        json_data = resp.json()
        assert json_data["success"] is True
        assert json_data["url"] == mock_meta["url"]
        assert json_data["key"] == mock_meta["key"]


def test_admin_api_upload_image_no_file(admin_client):
    """Admin upload endpoint returns 400 when no file is supplied."""
    resp = admin_client.post("/api/upload-image", data={"type": "writing"})
    assert resp.status_code == 400
    assert resp.json()["success"] is False


def test_admin_api_delete_image(admin_client):
    """Admin delete endpoint deletes the object from R2."""
    with patch("r2_storage.delete_image_from_r2", return_value=True) as mock_delete:
        resp = admin_client.post("/api/delete-image", json={"key": "images/writing/2026/11/abc.webp"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_delete.assert_called_once_with("images/writing/2026/11/abc.webp")


def test_public_detail_view_renders_featured_image(client):
    """Public article detail page renders the featured image if present."""
    mock_post = {
        "id": 101,
        "type": "writing",
        "title": "On Deliberate Architecture",
        "slug": "on-deliberate-architecture",
        "excerpt": "A study on structural elegance.",
        "content_markdown": "# Overview\n\nContent body here.",
        "is_published": True,
        "show_on_landing": True,
        "published_at": None,
        "updated_at": None,
        "tags": ["architecture"],
        "external_links": [],
        "seo_title": None,
        "seo_description": None,
        "continue_reading_slugs": [],
        "featured_image_url": "https://pub-r2.dev/images/writing/2026/11/cover.webp",
        "featured_image_alt": "Clean architecture diagram",
        "featured_image_width": 1200,
        "featured_image_height": 630
    }

    with patch("db.get_published_post_by_slug", return_value=mock_post), \
         patch("db.get_continue_reading_posts", return_value=[]):
        resp = client.get("/writing/on-deliberate-architecture")
        assert resp.status_code == 200
        html = resp.text
        assert 'class="detail-featured-image"' in html
        assert 'src="https://pub-r2.dev/images/writing/2026/11/cover.webp"' in html
        assert 'Clean architecture diagram' in html


def test_public_detail_view_without_image(client):
    """Articles without a featured image render cleanly without broken image tags."""
    mock_post = {
        "id": 102,
        "type": "books",
        "title": "Structure and Interpretation",
        "slug": "structure-and-interpretation",
        "excerpt": "Reading notes.",
        "content_markdown": "Notes content.",
        "is_published": True,
        "show_on_landing": False,
        "published_at": None,
        "updated_at": None,
        "tags": [],
        "external_links": [],
        "seo_title": None,
        "seo_description": None,
        "continue_reading_slugs": [],
        "featured_image_url": None,
        "featured_image_alt": None,
    }

    with patch("db.get_published_post_by_slug", return_value=mock_post), \
         patch("db.get_continue_reading_posts", return_value=[]):
        resp = client.get("/books/structure-and-interpretation")
        assert resp.status_code == 200
        assert 'class="detail-featured-image"' not in resp.text


def test_public_list_view_renders_card_images(client):
    """Archive listing pages display card images when available."""
    mock_posts = [
        {
            "id": 1,
            "type": "experiments",
            "title": "Distributed Consensus",
            "slug": "distributed-consensus",
            "excerpt": "Testing Raft.",
            "content_markdown": "Content.",
            "is_published": True,
            "show_on_landing": True,
            "published_at": None,
            "tags": ["consensus"],
            "featured_image_url": "https://pub-r2.dev/images/experiments/cover.webp",
            "featured_image_alt": "Raft Nodes"
        },
        {
            "id": 2,
            "type": "experiments",
            "title": "Memory Allocator",
            "slug": "memory-allocator",
            "excerpt": "Testing arena allocators.",
            "content_markdown": "Content.",
            "is_published": True,
            "show_on_landing": False,
            "published_at": None,
            "tags": ["c"],
            "featured_image_url": None,
            "featured_image_alt": None
        }
    ]

    with patch("db.get_published_posts", return_value=mock_posts):
        resp = client.get("/experiments")
        assert resp.status_code == 200
        html = resp.text
        # First post has image wrap
        assert "archive-card-image-wrap" in html
        assert "https://pub-r2.dev/images/experiments/cover.webp" in html
        # Both posts are rendered
        assert "Distributed Consensus" in html
        assert "Memory Allocator" in html


def test_external_ip_blocked_from_admin_image_upload():
    """External requests to the admin upload endpoint are rejected with 403 Forbidden."""
    from admin import admin_app
    from starlette.testclient import TestClient

    external_client = TestClient(admin_app, client=("192.168.1.100", 54321))
    raw_img = make_dummy_jpeg()
    files = {"file": ("test.jpg", raw_img, "image/jpeg")}

    resp = external_client.post("/api/upload-image", files=files)
    assert resp.status_code == 403
    assert "strictly accessible from localhost" in resp.text


def test_media_streaming_route(client):
    """The /media/{file_path:path} route streams R2 assets with immutable caching."""
    mock_s3 = MagicMock()
    mock_body = io.BytesIO(b"RIFFdummywebpdata")
    mock_s3.get_object.return_value = {
        "ContentType": "image/webp",
        "ContentLength": 17,
        "ETag": '"abc123etag"',
        "Body": mock_body,
    }

    with patch.object(r2_storage, "is_r2_configured", return_value=True), \
         patch.object(r2_storage, "get_r2_client", return_value=mock_s3):

        resp = client.get("/media/images/research/2026/11/sample.webp")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"
        assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert resp.content == b"RIFFdummywebpdata"
