"""
Tests for public editorial and content routes.
Covers home, about, topic archives, single post detail view, sitemap, robots.txt, and newsletter signups.
"""
from unittest.mock import patch


def test_home_page_status(client):
    """Verifies that the home page renders with status 200."""
    with patch("db.get_landing_selected_posts", return_value=[]), \
         patch("db.get_recent_published_posts", return_value=[]):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "MADE FOR NOTHING" in resp.text


def test_about_page_status(client):
    """Verifies that the about page renders with status 200."""
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "about" in resp.text.lower() or "research" in resp.text.lower()


def test_topic_archives_status(client):
    """Verifies that each topic archive page renders with status 200."""
    topic_endpoints = ["/writing", "/research", "/experiments", "/projects", "/books"]
    for endpoint in topic_endpoints:
        with patch("db.get_published_posts", return_value=[]):
            resp = client.get(endpoint)
            assert resp.status_code == 200


def test_post_detail_found(client):
    """Verifies that an existing post renders with title and markdown content."""
    mock_post = {
        "id": 1,
        "type": "writing",
        "slug": "durable-systems-manifesto",
        "title": "Durable Systems Manifesto",
        "excerpt": "A philosophy of durable computing.",
        "content_markdown": "# Durable Systems\n\nSoftware built to outlive its dependencies.",
        "is_published": True,
        "continue_reading_slugs": []
    }
    with patch("db.get_published_post_by_slug", return_value=mock_post):
        resp = client.get("/writing/durable-systems-manifesto")
        assert resp.status_code == 200
        assert "Durable Systems Manifesto" in resp.text
        assert "Software built to outlive" in resp.text


def test_post_detail_not_found(client):
    """Verifies that requesting a nonexistent post renders 404."""
    with patch("db.get_published_post_by_slug", return_value=None), \
         patch("db.get_recent_published_posts", return_value=[]):
        resp = client.get("/writing/non-existent-slug-xyz")
        assert resp.status_code == 404


def test_invalid_post_type_returns_404(client):
    """Verifies that invalid post types return 404."""
    with patch("db.get_recent_published_posts", return_value=[]):
        resp = client.get("/invalid_category/some-slug")
        assert resp.status_code == 404


def test_robots_txt(client):
    """Verifies robots.txt returns text/plain with Sitemap reference."""
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    assert "User-agent:" in resp.text
    assert "Sitemap:" in resp.text


def test_sitemap_xml(client):
    """Verifies sitemap.xml returns application/xml."""
    with patch("db.get_all_published_slugs", return_value=[]), \
         patch("db.get_published_courses", return_value=[]):
        resp = client.get("/sitemap.xml")
        assert resp.status_code == 200
        assert "xml" in resp.headers["content-type"]


def test_newsletter_subscribe_valid(client):
    """Verifies valid newsletter subscription succeeds."""
    with patch("db.add_subscriber", return_value={"created": True}):
        resp = client.post("/api/newsletter/subscribe", json={"email": "reader@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "added"


def test_newsletter_subscribe_invalid_email(client):
    """Verifies invalid email format is rejected with 400 Bad Request."""
    resp = client.post("/api/newsletter/subscribe", json={"email": "not-an-email"})
    assert resp.status_code in (400, 422)
