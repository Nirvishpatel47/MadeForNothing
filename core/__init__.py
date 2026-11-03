"""
Core package for MADE FOR NOTHING.
Contains configuration, security middleware, and cross-cutting constants.
"""
from .config import settings, TYPE_METADATA, ARCHIVE_SECTIONS
from .security import SecurityHeadersMiddleware

__all__ = [
    "settings",
    "TYPE_METADATA",
    "ARCHIVE_SECTIONS",
    "SecurityHeadersMiddleware",
]
