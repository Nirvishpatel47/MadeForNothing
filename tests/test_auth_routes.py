"""
Tests for authentication flows and security primitives.
Covers password hashing, JWT tokens, mobile number validation, login, register, and session logout.
"""
from unittest.mock import patch
import auth


def test_password_hashing():
    """Verifies password hashing produces valid salted PBKDF2 hash and verifies correctly."""
    pwd = "super-secure-password-123"
    hashed = auth.hash_password(pwd)
    assert hashed != pwd
    assert hashed.startswith("pbkdf2_sha256$")
    assert auth.verify_password(pwd, hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False


def test_jwt_token_creation_and_verification():
    """Verifies JWT token encoding, decoding, and tamper detection."""
    token = auth.create_access_token(user_id=10, email="test@example.com")
    assert isinstance(token, str) and len(token) > 20

    payload = auth.verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "10"
    assert payload["email"] == "test@example.com"

    # Tampered token should fail verification
    tampered = token[:-4] + "xxxx"
    assert auth.verify_access_token(tampered) is None


def test_mobile_number_validation():
    """Verifies mobile number cleaner accepts 10-15 digits and rejects invalid formats."""
    # Valid formats
    assert auth.validate_mobile_number("9876543210") == "9876543210"
    assert auth.validate_mobile_number("+91 98765 43210") == "+919876543210"
    assert auth.validate_mobile_number("987-654-3210") == "9876543210"

    # Invalid formats
    try:
        auth.validate_mobile_number("12345")
        assert False, "Should raise ValueError for too short mobile number"
    except ValueError:
        pass

    try:
        auth.validate_mobile_number("abcdefghijk")
        assert False, "Should raise ValueError for non-numeric mobile number"
    except ValueError:
        pass


def test_login_page_renders(client):
    """Verifies login page returns 200 and includes Continue with Google button."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "Sign In" in resp.text
    assert "Continue with Google" in resp.text


def test_register_page_renders(client):
    """Verifies register page returns 200 and includes mobile number field."""
    resp = client.get("/register")
    assert resp.status_code == 200
    assert "Create Account" in resp.text
    assert "Mobile Number" in resp.text


def test_register_action_rejects_password_mismatch(client):
    """Verifies registration fails when password and confirm_password do not match."""
    resp = client.post(
        "/register",
        data={
            "name": "Maya Lin",
            "email": "maya@example.com",
            "mobile_number": "9876543210",
            "password": "Password123!",
            "confirm_password": "DifferentPassword123!"
        }
    )
    assert resp.status_code == 400
    assert "Passwords do not match" in resp.text


def test_register_action_rejects_invalid_mobile(client):
    """Verifies registration fails when mobile number contains fewer than 7 digits."""
    resp = client.post(
        "/register",
        data={
            "name": "Maya Lin",
            "email": "maya@example.com",
            "mobile_number": "123",
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
    )
    assert resp.status_code == 400
    assert "valid mobile number" in resp.text.lower()


def test_register_action_rejects_short_password(client):
    """Verifies registration fails when password is less than 8 characters."""
    resp = client.post(
        "/register",
        data={
            "name": "Maya Lin",
            "email": "maya@example.com",
            "mobile_number": "9876543210",
            "password": "short",
            "confirm_password": "short"
        }
    )
    assert resp.status_code == 400
    assert "at least 8 characters" in resp.text


def test_api_auth_me_unauthenticated(client):
    """Verifies /api/auth/me returns authenticated: False when no session exists."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["user"] is None


def test_api_auth_me_authenticated(authenticated_client, mock_user):
    """Verifies /api/auth/me returns authenticated: True and user profile when logged in."""
    with patch("db.get_user_by_id", return_value=mock_user):
        resp = authenticated_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == mock_user["email"]


def test_logout(authenticated_client):
    """Verifies logging out clears the session cookie and redirects."""
    resp = authenticated_client.get("/logout", follow_redirects=False)
    assert resp.status_code in (302, 303)
    # Cookie should be expired or empty
    cookie_header = resp.headers.get("set-cookie", "")
    assert auth.COOKIE_NAME in cookie_header
