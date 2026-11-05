"""
Security Middleware and Helpers for MADE FOR NOTHING.
Provides security headers, input sanitization, and basic defense against common web vulnerabilities.
"""
import re
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Applies standard defensive HTTP security headers to every outgoing response.
    Protects against clickjacking, MIME-sniffing, XSS, and credential leakage.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Basic security headers
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        headers.setdefault("X-XSS-Protection", "1; mode=block")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

        # Content-Security-Policy (allows self, Google Fonts, MathJax, Firebase, Mux)
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://www.gstatic.com https://cdn.jsdelivr.net https://apis.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https: https://image.mux.com https://*.mux.com https://*.r2.dev https://*.cloudflarestorage.com; "
            "media-src 'self' blob: https: https://stream.mux.com https://*.mux.com; "
            "connect-src 'self' blob: https://*.googleapis.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://*.firebaseio.com https://*.firebaseapp.com https://api.mux.com https://stream.mux.com https://*.mux.com https://*.litix.io; "
            "frame-src 'self' https://*.firebaseapp.com https://*.firebase.com https://accounts.google.com; "
            "worker-src 'self' blob:; "
            "frame-ancestors 'self';"
        )
        headers.setdefault("Content-Security-Policy", csp)

        # HSTS only when served over HTTPS
        if request.url.scheme == "https" or settings.BASE_URL.startswith("https://"):
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

        return response


def sanitize_text_input(val: str, max_length: int = 1000) -> str:
    """
    Strips dangerous null bytes and control characters while preserving unicode text.
    """
    if not val:
        return ""
    # Remove null bytes and control characters except newline and tab
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", val)
    return cleaned.strip()[:max_length]
