"""
Security Tests for Defensive Headers, Input Sanitization, and Vulnerability Protection.
"""
from unittest.mock import patch
import markdown_utils
from core.security import sanitize_text_input


def test_defensive_security_headers_present(client):
    """
    Verifies all responses include essential defensive HTTP headers:
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Permissions-Policy
    - Content-Security-Policy
    """
    with patch("db.get_landing_selected_posts", return_value=[]), \
         patch("db.get_recent_published_posts", return_value=[]):
        resp = client.get("/")
        headers = resp.headers

        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "SAMEORIGIN"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert "strict-origin" in headers.get("referrer-policy", "")
        assert "camera=()" in headers.get("permissions-policy", "")
        csp = headers.get("content-security-policy", "")
        assert "default-src" in csp
        assert "frame-src" in csp
        assert "firebaseapp.com" in csp
        assert "stream.mux.com" in csp
        assert "worker-src" in csp
        assert "media-src" in csp


def test_markdown_sanitizer_removes_scripts():
    """Verifies that malicious <script> tags are neutralized in markdown rendering."""
    payload = "Hello world <script>alert('pwned')</script> welcome."
    cleaned = markdown_utils.sanitize_html(payload)
    assert "<script>" not in cleaned.lower()
    assert "alert" not in cleaned.lower()


def test_markdown_sanitizer_removes_inline_event_handlers():
    """Verifies inline event handlers (onerror, onclick, onload) are stripped."""
    payload = '<img src="invalid.jpg" onerror="alert(1)">'
    cleaned = markdown_utils.sanitize_html(payload)
    assert "onerror" not in cleaned.lower()


def test_markdown_sanitizer_removes_javascript_protocols():
    """Verifies javascript: URI pseudo-protocols in links are blocked."""
    payload = '<a href="javascript:alert(1)">Click here</a>'
    cleaned = markdown_utils.sanitize_html(payload)
    assert "javascript:" not in cleaned.lower()


def test_sanitize_text_input_strips_null_bytes():
    """Verifies dangerous null bytes and terminal control chars are removed."""
    raw = "Student Name\x00\x08with null bytes"
    cleaned = sanitize_text_input(raw)
    assert "\x00" not in cleaned
    assert "\x08" not in cleaned
    assert "Student Name" in cleaned
