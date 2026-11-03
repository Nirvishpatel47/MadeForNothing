"""
Tests for Admin Portal Security and Dashboard.
Verifies strictly-enforced localhost isolation middleware and administrative controls.
"""
from unittest.mock import patch
from starlette.testclient import TestClient
from admin import admin_app


def test_admin_rejects_external_ip():
    """
    Verifies that requests from non-local IP addresses are rejected
    with 403 Forbidden by the localhost security middleware.
    """
    # Create client simulating an external network client host
    client = TestClient(admin_app, client=("192.168.1.100", 54321))
    resp = client.get("/")
    assert resp.status_code == 403
    assert "strictly accessible from localhost" in resp.text


def test_admin_allows_localhost_client(admin_client):
    """
    Verifies that requests from localhost (127.0.0.1 / testclient)
    are permitted and render the admin dashboard.
    """
    with patch("db.get_filtered_posts_admin", return_value=[]), \
         patch("db.get_post_counts_admin", return_value={"total": 0, "published": 0, "drafts": 0}):
        resp = admin_client.get("/")
        assert resp.status_code == 200
        assert "STUDIO" in resp.text or "Dashboard" in resp.text
