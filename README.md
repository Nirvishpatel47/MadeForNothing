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
├── .env                     # Database URL, host/port settings
├── README.md                # Documentation and run instructions
├── db.py                    # Connection pool, schema init/migration, parameterized CRUD
├── markdown_utils.py        # Markdown rendering and HTML sanitization
├── app.py                   # Public FastAPI reader application
├── admin.py                 # Local-only Admin FastAPI application
├── seed.py                  # Database initialization and editorial seed data
├── static/
│   ├── css/
│   │   └── style.css        # Publication-grade styles (light/dark mode, typography)
│   └── js/
│       └── main.js          # Dark mode toggle, reading progress bar, copy-code helper
├── templates/
│   ├── base.html            # Base layout with SEO metadata & reading progress
│   ├── index.html           # Dedicated research landing experience (What, Work, Start Here)
│   ├── list.html            # Clean editorial archive lists (/writing, /research, etc.)
│   ├── detail.html          # Detail reader view with links & continue reading
│   ├── about.html           # Ethos, colophon, and architecture
│   ├── 404.html             # Clean 404 error page
│   └── sitemap.xml          # Dynamic XML sitemap
└── admin/
    ├── static/
    │   ├── css/
    │   │   └── admin.css    # Clean admin dashboard & split-editor styles
    │   └── js/
    │       └── admin.js     # Live markdown preview & link manager
    └── templates/
        ├── base.html        # Admin layout
        ├── dashboard.html   # Posts management table with landing status & filters
        └── form.html        # Post creation & edit form with Landing Page toggle
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

---

## Admin Capabilities

- **Show on Landing Page**: Explicit toggle `[x] Show on Landing Page ("Start Here")` grants full editorial control over what first-time visitors encounter on the homepage.
- **Draft & Publish**: Instant toggle; unlisted drafts are never indexed or visible publicly.
- **Split Markdown Editor**: Live side-by-side preview with debounced rendering.
- **Metadata Management**: Tags, external citations/links, and SEO title/description overrides.
- **Continue Reading**: Curate up to 3 related published entries per post.
