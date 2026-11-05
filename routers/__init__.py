"""
Routers package for MADE FOR NOTHING.
Organizes endpoints into cohesive, testable, and maintainable domain modules:
- public: Main editorial site, content archives, and newsletter
- auth: Authentication (Email/Password, Firebase, Google Sign-In)
- courses: Course catalog, course detail, and student dashboard
- lessons: Protected lesson viewer and interactive API endpoints
- payments: Direct peer-to-peer UPI settlement and UTR audit flow
"""
from .public import router as public_router
from .auth import router as auth_router
from .courses import router as courses_router
from .lessons import router as lessons_router
from .payments import router as payments_router
from .media import router as media_router

__all__ = [
    "public_router",
    "auth_router",
    "courses_router",
    "lessons_router",
    "payments_router",
    "media_router",
]
