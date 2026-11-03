"""
Tests for Course Enrollment Payment & UTR Audit Submission.
Covers 12-digit numeric UTR validation, rejection of 10-digit entries, duplicate checks, and authorization.
"""
from unittest.mock import patch


def test_payment_page_requires_login(client, sample_course):
    """Verifies unauthenticated user is redirected to login when visiting payment page."""
    resp = client.get(f"/courses/{sample_course['slug']}/enroll", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


def test_payment_page_renders_for_student(authenticated_client, sample_course):
    """Verifies authenticated student sees UPI ID, price, and UTR submission form."""
    with patch("db.get_published_course_by_slug", return_value=sample_course), \
         patch("db.is_user_enrolled", return_value=False), \
         patch("db.get_user_payment_for_course", return_value=None):
        resp = authenticated_client.get(f"/courses/{sample_course['slug']}/enroll")
        assert resp.status_code == 200
        assert "Submit Verification UTR" in resp.text
        assert "12-Digit UTR" in resp.text


def test_payment_rejects_10_digit_utr(authenticated_client, sample_course):
    """
    Verifies that entering 10 digits instead of 12 displays the simple error:
    'A 12-digit UTR number is compulsory. Please enter a valid 12-digit numeric UTR.'
    """
    with patch("db.get_published_course_by_slug", return_value=sample_course):
        resp = authenticated_client.post(
            f"/courses/{sample_course['slug']}/payment",
            data={
                "payment_reference": "1234567890",  # 10 digits
                "payer_name": "Test Payer",
                "payer_note": ""
            }
        )
        assert resp.status_code == 400
        assert "A 12-digit UTR number is compulsory" in resp.text


def test_payment_rejects_non_numeric_utr(authenticated_client, sample_course):
    """Verifies non-numeric characters are rejected."""
    with patch("db.get_published_course_by_slug", return_value=sample_course):
        resp = authenticated_client.post(
            f"/courses/{sample_course['slug']}/payment",
            data={
                "payment_reference": "ABCDEF123456",  # Non-numeric
                "payer_name": "Test Payer",
                "payer_note": ""
            }
        )
        assert resp.status_code == 400
        assert "A 12-digit UTR number is compulsory" in resp.text


def test_payment_accepts_valid_12_digit_utr(authenticated_client, sample_course):
    """Verifies that submitting a valid 12-digit numeric UTR registers the submission and redirects."""
    mock_submission = {
        "id": 99,
        "user_id": 42,
        "course_id": sample_course["id"],
        "amount": sample_course["price"],
        "payment_reference": "427189123456",
        "status": "pending"
    }
    with patch("db.get_published_course_by_slug", return_value=sample_course), \
         patch("db.get_payment_submission_by_reference", return_value=None), \
         patch("db.create_payment_submission", return_value=mock_submission):
        resp = authenticated_client.post(
            f"/courses/{sample_course['slug']}/payment",
            data={
                "payment_reference": "427189123456",  # Exactly 12 digits
                "payer_name": "Test Payer",
                "payer_note": "PhonePe"
            },
            follow_redirects=False
        )
        assert resp.status_code in (302, 303)
        assert f"/courses/{sample_course['slug']}/enroll" in resp.headers["location"]


def test_payment_handles_duplicate_utr(authenticated_client, sample_course):
    """Verifies duplicate 12-digit UTR submissions are detected and flagged."""
    existing_submission = {
        "id": 88,
        "user_id": 999,  # Different user
        "course_id": sample_course["id"],
        "payment_reference": "427189123456",
        "status": "pending"
    }
    with patch("db.get_published_course_by_slug", return_value=sample_course), \
         patch("db.get_payment_submission_by_reference", return_value=existing_submission):
        resp = authenticated_client.post(
            f"/courses/{sample_course['slug']}/payment",
            data={
                "payment_reference": "427189123456",
                "payer_name": "Duplicate Payer",
                "payer_note": ""
            }
        )
        assert resp.status_code == 400
        assert "already been submitted" in resp.text
