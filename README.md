# MADE FOR NOTHING

> **WRITE → PUBLISH → READ → EXPLORE**

A distinct, production-grade personal research website, digital notebook, and archive built with Python, FastAPI, Jinja2, and PostgreSQL (Supabase).

---

## Architectural & Design Ethos

- **Serious Independent Research Aesthetic**: Warm off-white paper tones, carbon ink typography, restrained grayscale, and generous whitespace. No AI-generated clutter, no startup landing page clichés, no marketing funnels, and no excessive card grids.
- **Dedicated Editorial Landing Page**: Answers *What is MADE FOR NOTHING?*, *What kind of work exists here?*, and *Where should I start?* with a curated "Start Here" selection.
- **Editorial Landing Control (`show_on_landing`)**: Published items only appear in the landing page selection if explicitly enabled via the admin toggle.
- **Zero `.sql` files**: All database tables, indexes, and schema evolutions are managed directly in Python using parameterized SQL.
- **Strictly Decoupled**: The public reader app (`app.py`) runs independently on port 8000 and requires no admin app to be running.
- **Local-Only Admin**: The administrative application (`admin.py`) binds strictly to `127.0.0.1:8001` and is protected by host verification middleware.
- **Sanitized Markdown**: Headings, tables, quotes, code blocks, lists, links, and horizontal rules are safely rendered and sanitized against XSS.

---

## Content Types

1. **Writing**: Longform essays, philosophical inquiries, and reflections on design and systems.
2. **Research**: Structured investigations, theoretical models, literature notes, and proofs.
3. **Experiments**: Technical prototypes, code tests, and performance benchmarks.
4. **Projects**: Finished tools, open-source software, and public artifacts.
5. **Books**: Marginalia, reading notes, and conceptual summaries.
6. **Videos**: Recorded lectures, technical demonstrations, architectural walkthroughs, and visual notes.

---

## Project Structure

```text
.
├── .env                     # Database URL, JWT secrets, Firebase, Mux settings
├── README.md                # Documentation and run instructions
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Dependencies (FastAPI, PyJWT, pytest, etc.)
├── db.py                    # Backward-compatible database facade (re-exports database/)
├── database/                # Modular domain-driven database layer
│   ├── __init__.py          # Exports all functions, schemas, and connection pools
│   ├── connection.py        # Connection pooling (psycopg2/3), dict rows & health checks
│   ├── schema.py            # DDL initialization & foreign key self-healing migrations
│   ├── posts.py             # Editorial posts, landing curation, tags, slugs & CRUD
│   ├── subscribers.py       # Newsletter registrations & unsubscribe queries
│   ├── users.py             # Enrolled users, mobile numbers & Firebase sync
│   ├── courses.py           # Courses, lessons, Mux video assets & Q&As
│   ├── enrollments.py       # Student enrollment verification & dashboard progress
│   ├── payments.py          # UPI submissions, 12-digit UTR checks & approval audits
│   └── progress.py          # Lesson watch progress & reflection self-assessments
├── auth.py                  # JWT session management & Firebase Authentication
├── markdown_utils.py        # Markdown rendering and HTML sanitization
├── mux_utils.py             # Mux video signed playback tokens
├── app.py                   # Public FastAPI application (modular router mount)
├── admin.py                 # Local-only Admin FastAPI application
├── seed.py                  # Database initialization and editorial seed data
├── core/                    # Core configuration & defensive security
│   ├── __init__.py          # Exports settings and security middleware
│   ├── config.py            # Centralized settings & type constants
│   └── security.py          # SecurityHeadersMiddleware & input sanitizers
├── routers/                 # Modular domain routers
│   ├── __init__.py          # Router aggregations
│   ├── public.py            # Editorial articles, archives, sitemap, robots
│   ├── auth.py              # Login, register, Google/Firebase auth, cookies
│   ├── courses.py           # Catalog, course detail, student dashboard
│   ├── lessons.py           # Protected lesson player, signed tokens, quiz APIs
│   └── payments.py          # Peer-to-peer UPI enrollment & 12-digit UTR audit
├── tests/                   # Automated verification test suite
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures and mock test clients
│   ├── run_all_tests.py     # Standalone test runner (python tests/run_all_tests.py)
│   ├── test_public_routes.py # Public reader & newsletter tests
│   ├── test_auth_routes.py  # Password hashing, JWT, registration & mobile tests
│   ├── test_courses_routes.py # Course catalog, syllabus, and dashboard tests
│   ├── test_payments_routes.py # 12-digit UTR validation & duplicate tests
│   ├── test_lessons_routes.py # Lesson enrollment gates & interactive APIs
│   ├── test_admin_routes.py # Localhost isolation & dashboard tests
│   └── test_security.py     # Security headers, XSS prevention, sanitization
├── static/
│   ├── css/style.css        # Publication styles (light/dark mode, responsive)
│   └── js/main.js           # Theme toggle, reading progress, copy helpers
├── templates/               # Public Jinja2 templates
└── admin/                   # Admin static assets & templates
```

---

## Getting Started

### 1. Requirements

- Python 3.10+
- PostgreSQL database (or Supabase PostgreSQL connection string in `.env`)
- Required packages:
  ```bash
  pip install fastapi uvicorn[standard] jinja2 markdown bleach python-dotenv psycopg2-binary
  ```

### 2. Initialize & Seed Database

Run the seed script to create all tables, apply schema columns, and populate initial editorial research posts:

```bash
python seed.py
```

### 3. Run the Public Site

Start the public reader app:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open:
- **Home (Landing Page)**: `http://localhost:8000/`
- **Writing**: `http://localhost:8000/writing`
- **Research**: `http://localhost:8000/research`
- **Experiments**: `http://localhost:8000/experiments`
- **Projects**: `http://localhost:8000/projects`
- **Books**: `http://localhost:8000/books`
- **About**: `http://localhost:8000/about`
- **Sitemap**: `http://localhost:8000/sitemap.xml`
- **Robots**: `http://localhost:8000/robots.txt`

### 4. Run the Local-Only Admin

In a separate terminal, launch the admin app:

```bash
uvicorn admin:admin_app --host 127.0.0.1 --port 8001 --reload
```

Open:
- **Admin Dashboard**: `http://127.0.0.1:8001/`

### 5. Run Automated Tests

To test the entire functionality of all modules (public routes, authentication, course catalog, payments, lessons, admin security, and defensive headers):

```bash
# Option A: Standalone test runner (runs pytest or falls back to unittest)
python tests/run_all_tests.py

# Option B: Run via pytest directly
pytest
```

---

## Admin Capabilities

- **Show on Landing Page**: Explicit toggle `[x] Show on Landing Page ("Start Here")` grants full editorial control over what first-time visitors encounter on the homepage.
- **Draft & Publish**: Instant toggle; unlisted drafts are never indexed or visible publicly.
- **Split Markdown Editor**: Live side-by-side preview with debounced rendering.
- **Metadata Management**: Tags, external citations/links, and SEO title/description overrides.
- **Continue Reading**: Curate up to 3 related published entries per post.
- **Course & Lesson Management**: Full editorial control over courses, units, and Q&As.
- **Mux Direct Upload & Signed Playback**: Secure signed video asset configuration.
- **Manual Payment Verification**: Approve or reject manual UPI UTR submissions with one click.

---

## Course System Architecture

```text
PUBLIC WEBSITE
    ↓
/courses & /courses/{slug}
    ↓
Student Sign-In / Register (HttpOnly JWT)
    ↓
Manual UPI Transfer & UTR Submission (/courses/{slug}/enroll)
    ↓
Status: Pending (Manual Verification)
    ↓
Instructor Approves Payment (/payments in Admin)
    ↓
Active Enrollment Granted Automatically
    ↓
Student Course Dashboard (/course/dashboard)
    ↓
Lesson Viewer with Signed Mux Video & Instructor Q&A (/courses/{slug}/lessons/{id})
```

