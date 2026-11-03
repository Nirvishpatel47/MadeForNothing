import os
import re
import time
import hmac
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Response
import jwt
from cryptography.x509 import load_pem_x509_certificate
import requests
from dotenv import load_dotenv

import db

load_dotenv()

logger = logging.getLogger("made_for_nothing.auth")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "mfn-default-jwt-secret-key-change-in-production-32chars")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24 * 7))  # Default 7 days
COOKIE_NAME = "__session"

# =============================================================================
# FIREBASE AUTHENTICATION CONFIGURATION
# =============================================================================

FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "").strip()
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "").strip()
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", "").strip()
FIREBASE_REQUIRE_EMAIL_VERIFICATION = os.getenv("FIREBASE_REQUIRE_EMAIL_VERIFICATION", "true").strip().lower() in ("true", "1", "yes")

FIREBASE_IDENTITY_BASE_URL = "https://identitytoolkit.googleapis.com/v1"
GOOGLE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_google_certs_cache: Dict[str, Any] = {"certs": {}, "expires_at": 0}


class FirebaseAuthError(Exception):
    """Structured exception for Firebase Authentication errors."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def is_firebase_enabled() -> bool:
    """Returns True when FIREBASE_API_KEY is configured in the environment."""
    return bool(FIREBASE_API_KEY)


def get_firebase_client_config() -> dict:
    """Returns public Firebase config for templates if needed."""
    return {
        "enabled": is_firebase_enabled(),
        "apiKey": FIREBASE_API_KEY,
        "projectId": FIREBASE_PROJECT_ID,
        "authDomain": FIREBASE_AUTH_DOMAIN or (f"{FIREBASE_PROJECT_ID}.firebaseapp.com" if FIREBASE_PROJECT_ID else ""),
        "requireEmailVerification": FIREBASE_REQUIRE_EMAIL_VERIFICATION,
    }


def _map_firebase_error(raw_code: str) -> str:
    """Translates Firebase Identity Toolkit error codes into friendly messages."""
    code = (raw_code or "").upper()
    if "EMAIL_EXISTS" in code:
        return "An account with this email address already exists. Please sign in instead."
    if "INVALID_LOGIN_CREDENTIALS" in code or "INVALID_PASSWORD" in code or "EMAIL_NOT_FOUND" in code:
        return "Invalid email address or password."
    if "USER_DISABLED" in code:
        return "This account has been disabled. Please contact support."
    if "TOO_MANY_ATTEMPTS_TRY_LATER" in code:
        return "Too many attempts. Please wait a few minutes and try again."
    if "WEAK_PASSWORD" in code:
        return "Password must be at least 6 characters long."
    if "INVALID_EMAIL" in code:
        return "Please enter a valid email address."
    if "OPERATION_NOT_ALLOWED" in code:
        return "Email/Password sign-in is not enabled in Firebase Console (Authentication -> Sign-in method)."
    if "API_KEY_INVALID" in code or "API key not valid" in raw_code:
        return "Firebase API Key is invalid. Please check FIREBASE_API_KEY in your .env file."
    return f"Authentication error ({raw_code}). Please try again."


def firebase_sign_up(email: str, password: str, display_name: str = "") -> dict:
    """
    Creates a new user in Firebase Authentication using Email & Password.
    Returns dict with idToken, refreshToken, localId (firebase_uid), and email.
    """
    if not is_firebase_enabled():
        raise FirebaseAuthError("FIREBASE_NOT_CONFIGURED", "Firebase API Key is not configured.")

    url = f"{FIREBASE_IDENTITY_BASE_URL}/accounts:signUp?key={FIREBASE_API_KEY}"
    payload = {
        "email": email.strip().lower(),
        "password": password,
        "returnSecureToken": True
    }
    if display_name:
        payload["displayName"] = display_name.strip()

    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
    except Exception as e:
        logger.error(f"Firebase signUp network error: {e}")
        raise FirebaseAuthError("NETWORK_ERROR", "Unable to reach Firebase Authentication service. Please check your connection.")

    if resp.status_code != 200 or "error" in data:
        raw_err = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        raise FirebaseAuthError(raw_err, _map_firebase_error(raw_err))

    return data


def firebase_send_verification_email(id_token: str) -> bool:
    """
    Requests Firebase to send an email verification link to the user's email.
    """
    if not is_firebase_enabled() or not id_token:
        return False

    url = f"{FIREBASE_IDENTITY_BASE_URL}/accounts:sendOobCode?key={FIREBASE_API_KEY}"
    payload = {
        "requestType": "VERIFY_EMAIL",
        "idToken": id_token
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning(f"Firebase sendOobCode VERIFY_EMAIL returned {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Error sending Firebase verification email: {e}")
        return False


def firebase_send_password_reset(email: str) -> bool:
    """
    Requests Firebase to send a password reset email to the given address.
    """
    if not is_firebase_enabled() or not email:
        return False

    url = f"{FIREBASE_IDENTITY_BASE_URL}/accounts:sendOobCode?key={FIREBASE_API_KEY}"
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email.strip().lower()
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Firebase password reset email: {e}")
        return False


def firebase_get_account_info(id_token: str) -> Optional[dict]:
    """
    Fetches authoritative Firebase account details (localId, email, emailVerified, displayName)
    using a valid Firebase ID token.
    """
    if not is_firebase_enabled() or not id_token:
        return None

    url = f"{FIREBASE_IDENTITY_BASE_URL}/accounts:lookup?key={FIREBASE_API_KEY}"
    try:
        resp = requests.post(url, json={"idToken": id_token}, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        users = data.get("users", [])
        if not users:
            return None
        return users[0]
    except Exception as e:
        logger.error(f"Error looking up Firebase account info: {e}")
        return None


def firebase_sign_in(email: str, password: str) -> dict:
    """
    Authenticates a user's email & password against Firebase Authentication,
    and fetches their account verification status.
    Returns dict with idToken, refreshToken, localId, email, emailVerified, displayName.
    """
    if not is_firebase_enabled():
        raise FirebaseAuthError("FIREBASE_NOT_CONFIGURED", "Firebase API Key is not configured.")

    url = f"{FIREBASE_IDENTITY_BASE_URL}/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email.strip().lower(),
        "password": password,
        "returnSecureToken": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
    except Exception as e:
        logger.error(f"Firebase signInWithPassword network error: {e}")
        raise FirebaseAuthError("NETWORK_ERROR", "Unable to reach Firebase Authentication service. Please check your connection.")

    if resp.status_code != 200 or "error" in data:
        raw_err = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        raise FirebaseAuthError(raw_err, _map_firebase_error(raw_err))

    id_token = data.get("idToken", "")
    acct_info = firebase_get_account_info(id_token) or {}
    if acct_info.get("disabled"):
        raise FirebaseAuthError("USER_DISABLED", _map_firebase_error("USER_DISABLED"))

    data["emailVerified"] = bool(acct_info.get("emailVerified", False))
    if acct_info.get("displayName") and not data.get("displayName"):
        data["displayName"] = acct_info.get("displayName")

    return data


def _get_google_public_certs() -> Dict[str, str]:
    """Fetches and caches Google's SecureToken X.509 certificates for verifying Firebase JWTs."""
    now = time.time()
    if _google_certs_cache["certs"] and now < _google_certs_cache["expires_at"]:
        return _google_certs_cache["certs"]

    try:
        resp = requests.get(GOOGLE_CERTS_URL, timeout=5)
        if resp.status_code == 200:
            _google_certs_cache["certs"] = resp.json()
            _google_certs_cache["expires_at"] = now + 3600
    except Exception as e:
        logger.warning(f"Failed to fetch Google public certs: {e}")

    return _google_certs_cache["certs"]


def firebase_verify_id_token(id_token: str) -> Optional[dict]:
    """
    Securely verifies a Firebase ID token via Google's X.509 public certificates
    and/or Firebase Identity Toolkit accounts:lookup endpoint.
    Treats Google-authenticated users with verified Google emails as email-verified.
    """
    if not id_token or not isinstance(id_token, str):
        return None

    decoded_claims = None

    # 1. Verify RS256 cryptographic signature using Google's SecureToken X.509 public certificates
    try:
        header = jwt.get_unverified_header(id_token)
        unverified_payload = jwt.decode(id_token, options={"verify_signature": False})
        kid = header.get("kid")
        aud = FIREBASE_PROJECT_ID or unverified_payload.get("aud", "")
        certs = _get_google_public_certs()
        if kid and kid in certs and aud:
            cert_obj = load_pem_x509_certificate(certs[kid].encode("utf-8"))
            public_key = cert_obj.public_key()
            decoded_claims = jwt.decode(
                id_token,
                public_key,
                algorithms=["RS256"],
                audience=aud,
                issuer=f"https://securetoken.google.com/{aud}"
            )
    except jwt.ExpiredSignatureError:
        logger.debug("Firebase ID token expired")
        return None
    except Exception as e:
        logger.debug(f"Firebase JWT RS256 verification fell back to lookup: {e}")

    # 2. Authoritative Firebase accounts:lookup check when FIREBASE_API_KEY is configured
    acct = firebase_get_account_info(id_token) if is_firebase_enabled() else None
    if acct and acct.get("disabled"):
        return None

    if decoded_claims:
        sign_in_provider = (decoded_claims.get("firebase") or {}).get("sign_in_provider", "")
        email = (decoded_claims.get("email") or (acct or {}).get("email") or "").strip().lower()
        is_google_provider = sign_in_provider == "google.com"
        email_verified = bool(
            decoded_claims.get("email_verified", False)
            or (acct or {}).get("emailVerified", False)
            or (is_google_provider and email)
        )
        return {
            "localId": decoded_claims.get("user_id") or decoded_claims.get("sub") or (acct or {}).get("localId"),
            "email": email,
            "emailVerified": email_verified,
            "displayName": decoded_claims.get("name") or (acct or {}).get("displayName") or "",
            "signInProvider": sign_in_provider or ("google.com" if is_google_provider else "password"),
        }

    if acct:
        providers = [p.get("providerId", "") for p in (acct.get("providerUserInfo") or [])]
        is_google_provider = "google.com" in providers
        email = (acct.get("email") or "").strip().lower()
        email_verified = bool(acct.get("emailVerified", False) or (is_google_provider and email))
        return {
            "localId": acct.get("localId"),
            "email": email,
            "emailVerified": email_verified,
            "displayName": acct.get("displayName", ""),
            "signInProvider": "google.com" if is_google_provider else (providers[0] if providers else "password"),
        }

    return None


# =============================================================================
# MOBILE NUMBER VALIDATION
# =============================================================================

def validate_mobile_number(mobile: str) -> str:
    """
    Validates and normalizes a user's mobile phone number.
    Accepts international or local formats (7 to 15 digits, optional leading +).
    Raises ValueError if invalid.
    """
    raw = (mobile or "").strip()
    if not raw:
        raise ValueError("Please provide your mobile number.")

    # Extract digits and optional leading '+'
    has_plus = raw.startswith("+")
    digits_only = re.sub(r"\D", "", raw)
    if len(digits_only) < 7 or len(digits_only) > 15:
        raise ValueError("Please enter a valid mobile number (10 to 15 digits).")

    return f"+{digits_only}" if has_plus else digits_only


# =============================================================================
# PASSWORD HASHING (PBKDF2-HMAC-SHA256)
# =============================================================================

def hash_password(password: str) -> str:
    """Securely hash a password with random salt and PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against the stored hash in constant time."""
    if not hashed_password or not plain_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]

        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations
        )
        return hmac.compare_digest(dk.hex(), expected_hash)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


# =============================================================================
# APPLICATION JWT
# =============================================================================

def create_access_token(
    user_id: int,
    email: str,
    firebase_uid: Optional[str] = None,
    expires_in_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """Generate an Application JWT for user session authentication."""
    expire = int(time.time()) + (expires_in_minutes * 60)
    payload = {
        "sub": str(user_id),
        "email": email,
        "firebase_uid": firebase_uid or "",
        "iat": int(time.time()),
        "exp": expire,
        "type": "app_auth"
    }
    encoded = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate an Application JWT."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "app_auth":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Access token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid access token: {e}")
        return None


# =============================================================================
# COOKIE MANAGEMENT & DEPENDENCIES
# =============================================================================

def set_auth_cookie(response: Response, token: str, secure: bool = False):
    """Set HttpOnly session cookie."""
    max_age = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age,
        expires=max_age,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure
    )


def clear_auth_cookie(response: Response):
    """Clear HttpOnly session cookie on logout."""
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax"
    )


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract token from either HttpOnly cookie or Authorization Bearer header."""
    # 1. HttpOnly cookie (preferred for web reader/course navigation)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token

    # 2. Authorization header fallback
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()

    return None


def get_current_user_optional(request: Request) -> Optional[dict]:
    """Dependency that returns the authenticated user if valid token exists, else None."""
    token = extract_token_from_request(request)
    if not token:
        return None

    # 1. Check Application Session JWT
    payload = decode_access_token(token)
    if payload:
        user_id_str = payload.get("sub")
        if user_id_str:
            try:
                user_id = int(user_id_str)
                user = db.get_user_by_id(user_id)
                if user and user.get("is_active", True):
                    return user
            except Exception as e:
                logger.error(f"Error fetching current user {user_id_str}: {e}")

    # 2. Fallback: Check if a direct Firebase ID Token was supplied in Authorization header
    if is_firebase_enabled():
        fb_info = firebase_verify_id_token(token)
        if fb_info and fb_info.get("email"):
            try:
                user = db.sync_firebase_user(
                    email=fb_info["email"],
                    name=fb_info.get("displayName", ""),
                    firebase_uid=fb_info.get("localId"),
                    email_verified=fb_info.get("emailVerified", False)
                )
                if user and user.get("is_active", True):
                    return user
            except Exception as e:
                logger.error(f"Error syncing Firebase user from token: {e}")

    return None


def get_current_user_required(request: Request) -> dict:
    """Dependency that ensures user is authenticated, otherwise raises 401."""
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
