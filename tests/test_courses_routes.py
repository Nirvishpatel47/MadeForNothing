"""
Tests for Course Discovery and Student Studio Dashboard.
Covers public catalog, course syllabus detail, and student enrolled progress.
"""
from unittest.mock import patch


def test_courses_list_page(client, sample_course):
    """Verifies course catalog lists published courses."""
    with patch("db.get_published_courses", return_value=[sample_course]):
        resp = client.get("/courses")
        assert resp.status_code == 200
        assert sample_course["title"] in resp.text


def test_courses_alias_course(client, sample_course):
    """Verifies /course alias functions identically to /courses."""
    with patch("db.get_published_courses", return_value=[sample_course]):
        resp = client.get("/course")
        assert resp.status_code == 200
        assert sample_course["title"] in resp.text


def test_student_dashboard_requires_login(client):
    """Verifies accessing dashboard unauthenticated redirects to login."""
    resp = client.get("/courses/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


def test_student_dashboard_authenticated(authenticated_client, mock_user, sample_course):
    """Verifies accessing dashboard with authenticated session renders 200."""
    with patch("db.get_user_enrolled_courses", return_value=[sample_course]), \
         patch("db.get_course_progress_for_user", return_value={"lessons": []}), \
         patch("db.get_published_lessons_by_course", return_value=[]), \
         patch("db.get_payment_submissions_admin", return_value=[]):
        resp = authenticated_client.get("/courses/dashboard")
        assert resp.status_code == 200
        assert "Studio Dashboard" in resp.text or "Courses" in resp.text


def test_course_detail_found(client, sample_course, sample_lesson):
    """Verifies published course detail page renders title, lessons, and enrollment details."""
    with patch("db.get_published_course_by_slug", return_value=sample_course), \
         patch("db.get_published_lessons_by_course", return_value=[sample_lesson]), \
         patch("db.is_user_enrolled", return_value=False), \
         patch("db.get_user_payment_for_course", return_value=None):
        resp = client.get(f"/courses/{sample_course['slug']}")
        assert resp.status_code == 200
        assert sample_course["title"] in resp.text
        assert sample_lesson["title"] in resp.text


def test_course_detail_not_found(client):
    """Verifies requesting non-existent course returns 404."""
    with patch("db.get_published_course_by_slug", return_value=None), \
         patch("db.get_course_by_slug_admin", return_value=None), \
         patch("db.get_recent_published_posts", return_value=[]):
        resp = client.get("/courses/non-existent-course-slug")
        assert resp.status_code == 404
