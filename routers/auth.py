"""
Authentication Routes for MADE FOR NOTHING.
Covers Email/Password signup & login, Firebase Authentication, Google Sign-In,
password resets, email verification resend, session cookies, and user state endpoints.
"""
import logging
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Request, Form, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import db
import auth
from core.config import settings

logger = logging.getLogger("made_for_nothing.auth")
router = APIRouter()
templates = Jinja2Templates(directory=settings.TEMPLATES_DIR)


# --- Pydantic Schemas for JSON APIs ---

class LoginSchema(BaseModel):
    email: str
    password: str


class RegisterSchema(BaseModel):
    name: str
    email: str
    mobile_number: str
    password: str


class FirebaseTokenSchema(BaseModel):
    id_token: str
    name: Optional[str] = ""
    mobile_number: Optional[str] = ""
    next: Optional[str] = ""


# --- HTML Authentication Views ---

@router.get("/login", response_class=HTMLResponse)
def login_page( request: Request, next: Optional[str] = None, email: Optional[str] = None, verified_sent: Optional[str] = None ):
    current_user = auth.get_current_user_optional(request)
    if current_user:
        return RedirectResponse(next or "/course/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    msg = None
    if verified_sent == "1":
        msg = "Account created! We have sent a verification link to your email address. Please verify your email and sign in below."

    return templates.TemplateResponse("login.html", {
        "request": request,
        "current_user": None,
        "current_type": "auth",
        "next_url": next,
        "email": (email or "").strip(),
        "error": None,
        "message": msg,
        "needs_verification": False,
        "verification_token": None,
        "firebase_enabled": auth.is_firebase_enabled(),
        "firebase_config": auth.get_firebase_client_config(),
        "canonical_url": f"{settings.BASE_URL}/login",
        "base_url": settings.BASE_URL
    })


@router.post("/login", response_class=HTMLResponse)
async def login_action( request: Request, email: str = Form(...), password: str = Form(...), next: Optional[str] = Form(None) ):
    email_clean = email.strip().lower()

    if auth.is_firebase_enabled():
        try:
            fb_data = auth.firebase_sign_in(email_clean, password)
        except auth.FirebaseAuthError as fb_err:
            # Automatic migration if user existed in Supabase prior to Firebase integration
            existing_local = db.get_user_by_email(email_clean)
            if (
                existing_local
                and not existing_local.get("firebase_uid")
                and auth.verify_password(password, existing_local.get("password_hash", ""))
            ):
                try:
                    fb_signup = auth.firebase_sign_up(email_clean, password, existing_local.get("name", ""))
                    auth.firebase_send_verification_email(fb_signup.get("idToken", ""))
                    fb_data = {
                        "idToken": fb_signup.get("idToken", ""),
                        "localId": fb_signup.get("localId", ""),
                        "email": email_clean,
                        "emailVerified": False,
                        "displayName": existing_local.get("name", "")
                    }
                except auth.FirebaseAuthError:
                    return templates.TemplateResponse("login.html", {
                        "request": request,
                        "current_user": None,
                        "current_type": "auth",
                        "next_url": next,
                        "email": email_clean,
                        "error": fb_err.message,
                        "message": None,
                        "needs_verification": False,
                        "verification_token": None,
                        "firebase_enabled": True,
                        "firebase_config": auth.get_firebase_client_config(),
                        "canonical_url": f"{settings.BASE_URL}/login",
                        "base_url": settings.BASE_URL
                    }, status_code=status.HTTP_401_UNAUTHORIZED)
            else:
                return templates.TemplateResponse("login.html", {
                    "request": request,
                    "current_user": None,
                    "current_type": "auth",
                    "next_url": next,
                    "email": email_clean,
                    "error": fb_err.message,
                    "message": None,
                    "needs_verification": False,
                    "verification_token": None,
                    "firebase_enabled": True,
                    "firebase_config": auth.get_firebase_client_config(),
                    "canonical_url": f"{settings.BASE_URL}/login",
                    "base_url": settings.BASE_URL
                }, status_code=status.HTTP_401_UNAUTHORIZED)

        # Sync user record with Supabase
        pwd_hash = auth.hash_password(password)
        user = db.sync_firebase_user(
            email=email_clean,
            name=fb_data.get("displayName", ""),
            firebase_uid=fb_data.get("localId"),
            email_verified=fb_data.get("emailVerified", False),
            password_hash=pwd_hash
        )

        # Enforce Firebase Email Verification if enabled
        if auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION and not fb_data.get("emailVerified", False):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "current_user": None,
                "current_type": "auth",
                "next_url": next,
                "email": email_clean,
                "error": "Please verify your email address before signing in. Check your inbox for the Firebase verification link.",
                "message": None,
                "needs_verification": True,
                "verification_token": fb_data.get("idToken", ""),
                "firebase_enabled": True,
                "firebase_config": auth.get_firebase_client_config(),
                "canonical_url": f"{settings.BASE_URL}/login",
                "base_url": settings.BASE_URL
            }, status_code=status.HTTP_403_FORBIDDEN)

    else:
        # Local Supabase fallback when FIREBASE_API_KEY is not set
        user = db.get_user_by_email(email_clean)
        if not user or not auth.verify_password(password, user.get("password_hash", "")):
            return templates.TemplateResponse("login.html", {
                "request": request,
                "current_user": None,
                "current_type": "auth",
                "next_url": next,
                "email": email_clean,
                "error": "Invalid email address or password.",
                "message": None,
                "needs_verification": False,
                "verification_token": None,
                "firebase_enabled": False,
                "firebase_config": auth.get_firebase_client_config(),
                "canonical_url": f"{settings.BASE_URL}/login",
                "base_url": settings.BASE_URL
            }, status_code=status.HTTP_401_UNAUTHORIZED)

    if not user.get("is_active", True):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "current_user": None,
            "current_type": "auth",
            "next_url": next,
            "email": email_clean,
            "error": "Account is inactive. Please contact support.",
            "message": None,
            "needs_verification": False,
            "verification_token": None,
            "firebase_enabled": auth.is_firebase_enabled(),
            "firebase_config": auth.get_firebase_client_config(),
            "canonical_url": f"{settings.BASE_URL}/login",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_403_FORBIDDEN)

    token = auth.create_access_token(user["id"], user["email"], firebase_uid=user.get("firebase_uid"))
    redirect_target = next if (next and next.startswith("/")) else "/course/dashboard"
    response = RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    auth.set_auth_cookie(response, token)
    return response


@router.post("/resend-verification", response_class=HTMLResponse)
async def resend_verification_action( request: Request, email: str = Form(""), verification_token: str = Form(""), next: Optional[str] = Form(None) ):
    email_clean = email.strip().lower()
    sent = False
    if verification_token and auth.is_firebase_enabled():
        sent = auth.firebase_send_verification_email(verification_token)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "current_user": None,
        "current_type": "auth",
        "next_url": next,
        "email": email_clean,
        "error": None if sent else "Could not resend verification email automatically. Please sign in again to request a new link.",
        "message": "Verification email sent! Please check your inbox (and spam folder), click the link, and sign in." if sent else None,
        "needs_verification": False,
        "verification_token": None,
        "firebase_enabled": auth.is_firebase_enabled(),
        "firebase_config": auth.get_firebase_client_config(),
        "canonical_url": f"{settings.BASE_URL}/login",
        "base_url": settings.BASE_URL
    })


@router.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_action( request: Request, email: str = Form(...), next: Optional[str] = Form(None) ):
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "current_user": None,
            "current_type": "auth",
            "next_url": next,
            "email": email_clean,
            "error": "Please enter your email address to receive a password reset link.",
            "message": None,
            "needs_verification": False,
            "verification_token": None,
            "firebase_enabled": auth.is_firebase_enabled(),
            "firebase_config": auth.get_firebase_client_config(),
            "canonical_url": f"{settings.BASE_URL}/login",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)

    if auth.is_firebase_enabled():
        auth.firebase_send_password_reset(email_clean)
        msg = f"If an account exists for {email_clean}, Firebase has sent a password reset link to your email."
        err = None
    else:
        msg = None
        err = "Firebase Authentication is not configured yet (FIREBASE_API_KEY missing in .env)."

    return templates.TemplateResponse("login.html", {
        "request": request,
        "current_user": None,
        "current_type": "auth",
        "next_url": next,
        "email": email_clean,
        "error": err,
        "message": msg,
        "needs_verification": False,
        "verification_token": None,
        "firebase_enabled": auth.is_firebase_enabled(),
        "firebase_config": auth.get_firebase_client_config(),
        "canonical_url": f"{settings.BASE_URL}/login",
        "base_url": settings.BASE_URL
    })


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, next: Optional[str] = None):
    current_user = auth.get_current_user_optional(request)
    if current_user:
        return RedirectResponse(next or "/course/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse("register.html", {
        "request": request,
        "current_user": None,
        "current_type": "auth",
        "next_url": next,
        "name": "",
        "email": "",
        "mobile_number": "",
        "error": None,
        "message": None,
        "firebase_enabled": auth.is_firebase_enabled(),
        "firebase_config": auth.get_firebase_client_config(),
        "canonical_url": f"{settings.BASE_URL}/register",
        "base_url": settings.BASE_URL
    })


@router.post("/register", response_class=HTMLResponse)
async def register_action( request: Request, name: str = Form(...), email: str = Form(...), mobile_number: str = Form(...), password: str = Form(...), confirm_password: Optional[str] = Form(None), next: Optional[str] = Form(None) ):
    email_clean = email.strip().lower()
    name_clean = name.strip()
    mobile_raw = mobile_number.strip()

    def _render_reg_error(err_msg: str):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "current_user": None,
            "current_type": "auth",
            "next_url": next,
            "name": name_clean,
            "email": email_clean,
            "mobile_number": mobile_raw,
            "error": err_msg,
            "message": None,
            "firebase_enabled": auth.is_firebase_enabled(),
            "firebase_config": auth.get_firebase_client_config(),
            "canonical_url": f"{settings.BASE_URL}/register",
            "base_url": settings.BASE_URL
        }, status_code=status.HTTP_400_BAD_REQUEST)

    if not name_clean:
        return _render_reg_error("Please enter your full name.")

    if not email_clean or "@" not in email_clean:
        return _render_reg_error("Please provide a valid email address.")

    try:
        mobile_clean = auth.validate_mobile_number(mobile_raw)
    except ValueError as ve:
        return _render_reg_error(str(ve))

    if len(password) < 8:
        return _render_reg_error("Password must be at least 8 characters long.")

    if confirm_password is not None and password != confirm_password:
        return _render_reg_error("Passwords do not match. Please verify both fields.")

    existing_user = db.get_user_by_email(email_clean)
    if existing_user and (not auth.is_firebase_enabled() or existing_user.get("firebase_uid")):
        return _render_reg_error("An account with this email address already exists. Please sign in instead.")

    pwd_hash = auth.hash_password(password)
    firebase_uid = None
    id_token = None

    if auth.is_firebase_enabled():
        try:
            fb_data = auth.firebase_sign_up(email_clean, password, display_name=name_clean)
            firebase_uid = fb_data.get("localId")
            id_token = fb_data.get("idToken")
            if id_token:
                auth.firebase_send_verification_email(id_token)
        except auth.FirebaseAuthError as fb_err:
            return _render_reg_error(fb_err.message)

    try:
        new_user = db.sync_firebase_user(
            email=email_clean,
            name=name_clean,
            mobile_number=mobile_clean,
            firebase_uid=firebase_uid,
            email_verified=False,
            password_hash=pwd_hash
        )

        # If Firebase Email Verification is required, redirect to login with verification notice
        if auth.is_firebase_enabled() and auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION:
            next_param = f"&next={quote(next)}" if (next and next.startswith("/")) else ""
            login_redirect = f"/login?verified_sent=1&email={quote(email_clean)}{next_param}"
            return RedirectResponse(login_redirect, status_code=status.HTTP_303_SEE_OTHER)

        token = auth.create_access_token(new_user["id"], new_user["email"], firebase_uid=firebase_uid)
        redirect_target = next if (next and next.startswith("/")) else "/course/dashboard"
        response = RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)
        auth.set_auth_cookie(response, token)
        return response
    except Exception as e:
        logger.error(f"Error registering user {email_clean}: {e}")
        err_str = str(e)
        if "unique" in err_str.lower() or "duplicate" in err_str.lower():
            err_msg = "An account with this email address already exists. Please sign in."
        else:
            err_msg = f"Failed to create account: {e}"
        return _render_reg_error(err_msg)


@router.get("/logout")
def logout(response: Response, next: Optional[str] = None):
    redirect_target = next if (next and next.startswith("/")) else "/"
    resp = RedirectResponse(redirect_target, status_code=status.HTTP_303_SEE_OTHER)
    auth.clear_auth_cookie(resp)
    return resp


# --- JSON Authentication APIs ---

@router.post("/api/auth/login")
def api_login(data: LoginSchema, response: Response):
    if len(data.password) > 128:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    email_clean = data.email.strip().lower()

    if auth.is_firebase_enabled():
        try:
            fb_data = auth.firebase_sign_in(email_clean, data.password)
        except auth.FirebaseAuthError as fb_err:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=fb_err.message)

        if auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION and not fb_data.get("emailVerified", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email address via the Firebase link sent to your inbox."
            )

        user = db.sync_firebase_user(
            email=email_clean,
            name=fb_data.get("displayName", ""),
            firebase_uid=fb_data.get("localId"),
            email_verified=fb_data.get("emailVerified", False),
            password_hash=auth.hash_password(data.password)
        )
    else:
        user = db.get_user_by_email(email_clean)
        if not user or not auth.verify_password(data.password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive. Please contact support.")

    token = auth.create_access_token(user["id"], user["email"], firebase_uid=user.get("firebase_uid"))
    auth.set_auth_cookie(response, token)
    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "mobile_number": user.get("mobile_number", ""),
            "firebase_uid": user.get("firebase_uid")
        }
    }


@router.post("/api/auth/register")
def api_register(data: RegisterSchema, response: Response):
    password = data.password
    email_clean = data.email.strip().lower()
    name_clean = data.name.strip()

    try:
        mobile_clean = auth.validate_mobile_number(data.mobile_number)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    if not 8 <= len(password) <= 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be between 8 and 128 characters long.")

    pwd_hash = auth.hash_password(password)
    firebase_uid = None

    if auth.is_firebase_enabled():
        try:
            fb_data = auth.firebase_sign_up(email_clean, password, display_name=name_clean)
            firebase_uid = fb_data.get("localId")
            if fb_data.get("idToken"):
                auth.firebase_send_verification_email(fb_data["idToken"])
        except auth.FirebaseAuthError as fb_err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=fb_err.message)
    else:
        if db.get_user_by_email(email_clean):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")

    try:
        user = db.sync_firebase_user(
            email=email_clean,
            name=name_clean,
            mobile_number=mobile_clean,
            firebase_uid=firebase_uid,
            email_verified=False,
            password_hash=pwd_hash
        )
        token = auth.create_access_token(user["id"], user["email"], firebase_uid=firebase_uid)
        if not (auth.is_firebase_enabled() and auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION):
            auth.set_auth_cookie(response, token)
        return {
            "success": True,
            "verification_email_sent": auth.is_firebase_enabled(),
            "token": token if not (auth.is_firebase_enabled() and auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION) else None,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "mobile_number": user.get("mobile_number", ""),
                "firebase_uid": user.get("firebase_uid")
            }
        }
    except Exception:
        logger.exception("Error creating account")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to create account.")


@router.post("/api/auth/firebase")
@router.post("/api/auth/google")
def api_firebase_token_exchange(data: FirebaseTokenSchema, response: Response):
    """
    Verifies a Firebase ID Token (from Google Sign-In or Firebase Auth) securely on the backend,
    creates or syncs the user profile in Supabase without duplicates, and sets the session cookie.
    """
    fb_info = auth.firebase_verify_id_token(data.id_token)
    if not fb_info or not fb_info.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired Google/Firebase authentication token.")

    is_google = fb_info.get("signInProvider") == "google.com"
    is_email_verified = bool(fb_info.get("emailVerified", False) or is_google)

    if auth.FIREBASE_REQUIRE_EMAIL_VERIFICATION and not is_email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email address before signing in.")

    mobile_clean = ""
    if data.mobile_number and data.mobile_number.strip():
        try:
            mobile_clean = auth.validate_mobile_number(data.mobile_number)
        except ValueError as ve:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    user = db.sync_firebase_user(
        email=fb_info["email"],
        name=(data.name or fb_info.get("displayName") or "").strip(),
        mobile_number=mobile_clean,
        firebase_uid=fb_info.get("localId"),
        email_verified=is_email_verified
    )

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive. Please contact support.")

    token = auth.create_access_token(user["id"], user["email"], firebase_uid=user.get("firebase_uid"))
    auth.set_auth_cookie(response, token)
    redirect_target = data.next if (data.next and data.next.startswith("/")) else "/courses/dashboard"
    return {
        "success": True,
        "token": token,
        "redirect_url": redirect_target,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "mobile_number": user.get("mobile_number", ""),
            "firebase_uid": user.get("firebase_uid"),
            "email_verified": user.get("email_verified", False)
        }
    }


@router.post("/api/auth/logout")
def api_logout(response: Response):
    auth.clear_auth_cookie(response)
    return {"success": True}


@router.get("/api/auth/me")
def api_me(request: Request):
    user = auth.get_current_user_optional(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}
