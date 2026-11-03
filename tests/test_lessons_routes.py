"""
Tests for Lesson View & Interactive Student APIs.
Covers enrollment access gates, signed video playback tokens, progress updates, and quiz reflection submissions.
"""
from unittest.mock import patch


def test_lesson_view_requires_login(client, sample_course, sample_lesson):
    """Verifies accessing lesson view unauthenticated redirects to login."""
    resp = client.get(
        f"/courses/{sample_course['slug']}/lessons/{sample_lesson['id']}",
        follow_redirects=False
    )
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


def test_lesson_view_requires_enrollment(authenticated_client, sample_course, sample_lesson):
    """Verifies authenticated student who is NOT enrolled is redirected to the course syllabus."""
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=False):
        resp = authenticated_client.get(
            f"/courses/{sample_course['slug']}/lessons/{sample_lesson['id']}",
            follow_redirects=False
        )
        assert resp.status_code in (302, 303)
        assert f"/courses/{sample_course['slug']}" in resp.headers["location"]


def test_lesson_view_renders_for_enrolled_student(authenticated_client, sample_course, sample_lesson):
    """Verifies enrolled student can view the lesson player and curriculum content."""
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=True), \
         patch("db.get_course_by_id", return_value=sample_course), \
         patch("db.get_published_lessons_by_course", return_value=[sample_lesson]), \
         patch("db.get_course_progress_for_user", return_value={"lessons": []}), \
         patch("db.get_lesson_progress", return_value=None), \
         patch("db.get_questions_by_lesson", return_value=[]), \
         patch("db.get_student_responses_for_lesson", return_value={}):
        resp = authenticated_client.get(
            f"/courses/{sample_course['slug']}/lessons/{sample_lesson['id']}"
        )
        assert resp.status_code == 200
        assert sample_lesson["title"] in resp.text


def test_playback_token_requires_enrollment(authenticated_client, sample_lesson):
    """Verifies requesting Mux playback token without enrollment is rejected with 403 Forbidden."""
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=False):
        resp = authenticated_client.get(f"/api/course/lessons/{sample_lesson['id']}/playback-token")
        assert resp.status_code == 403


def test_playback_token_success_for_enrolled_student(authenticated_client, sample_lesson):
    """Verifies enrolled student receives signed playback token."""
    mock_tokens = {
        "playback": "signed_playback_jwt_test",
        "thumbnail": "signed_thumb_jwt_test",
        "storyboard": "signed_storyboard_jwt_test"
    }
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=True), \
         patch("mux_utils.generate_all_tokens", return_value=mock_tokens):
        resp = authenticated_client.get(f"/api/course/lessons/{sample_lesson['id']}/playback-token")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["token"] == "signed_playback_jwt_test"


def test_update_lesson_progress(authenticated_client, sample_lesson):
    """Verifies updating watch position and completion status."""
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=True), \
         patch("db.save_lesson_progress", return_value={"completed": True, "last_position_seconds": 360}):
        resp = authenticated_client.post(
            f"/api/course/lessons/{sample_lesson['id']}/progress",
            json={"completed": True, "last_position_seconds": 360}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["progress"]["completed"] is True


def test_submit_question_response(authenticated_client, sample_lesson):
    """Verifies student can submit answers to curriculum reflection questions."""
    mock_question = {
        "id": 501,
        "lesson_id": sample_lesson["id"],
        "question": "Why use WAL?",
        "answer": "WAL guarantees durability before mutating in-memory memtables."
    }
    with patch("db.get_lesson_by_id", return_value=sample_lesson), \
         patch("db.is_user_enrolled", return_value=True), \
         patch("db.get_question_by_id", return_value=mock_question), \
         patch("db.upsert_student_question_response", return_value={"id": 1, "student_answer": "Durability"}):
        resp = authenticated_client.post(
            f"/api/course/lessons/{sample_lesson['id']}/questions/501/response",
            json={"answer": "Durability"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["instructor_answer"] == mock_question["answer"]
