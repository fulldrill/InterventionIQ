# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

SPIP (Student Proficiency Insight Platform) is a multi-tenant teacher-facing web app that ingests Reveal Math assessment CSVs, maps questions to Maryland CCSS standards, renders interactive analytics, and provides an AI instructional assistant via Claude API + RAG.

## Commands

### Backend (FastAPI)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend (Next.js 14)

```bash
cd frontend
npm install
npm run dev      # dev server at http://localhost:3000
npm run build
npm run lint
```

### Docker (full stack)

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head   # run migrations
docker compose exec backend python scripts/seed_db.py  # seed sample data
```

### Database Migrations (Alembic)

```bash
# Apply migrations
docker compose exec backend alembic upgrade head

# Create new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "describe change"

# Rollback one
docker compose exec backend alembic downgrade -1
```

### Local dev email (Mailpit)

```bash
docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit
# View emails at http://localhost:8025
# Set SMTP_HOST=localhost SMTP_PORT=1025 in .env
```

API docs (dev only): http://localhost:8000/docs

## Architecture

### Backend (`backend/`)

- **`main.py`** — FastAPI app entry point; registers routers, CORS, and global error handler
- **`core/config.py`** — Pydantic settings loaded from `.env`
- **`core/database.py`** — Async SQLAlchemy engine + `get_db` dependency
- **`core/security.py`** — JWT encode/decode, Argon2id hashing, AES-256-GCM field encryption, `pseudonymize_student()`
- **`core/dependencies.py`** — FastAPI dependency injection: `get_current_user`, role guards (`get_current_active_teacher`, `get_current_school_admin`, `get_current_super_admin`), and `log_audit_event()`
- **`routers/`** — `auth.py`, `analytics.py`, `health.py` (and assessments/ai/admin routers)
- **`services/ai_service.py`** — RAG pipeline: pgvector similarity search → anonymized context assembly → Claude API call → parse `chart_spec` or text response
- **`services/csv_ingestion.py`** — Parses Reveal Math CSVs and question metadata CSVs
- **`services/proficiency.py`** — Calculates proficiency by student, class, standard, question type
- **`services/root_cause.py`** — Root cause analysis on low-performing standards
- **`models/`** — SQLAlchemy ORM models; `models/user.py` includes `User`, `models/audit.py` includes `AuditLog`
- **`migrations/`** — Alembic migrations; never auto-create tables in production

### Frontend (`frontend/src/`)

- **`lib/api.ts`** — Central API client with automatic JWT injection and silent refresh token rotation (on 401, retries once with refreshed token, redirects to `/login` on failure). All API calls go through `apiFetch`. Domain-specific helpers: `analyticsApi`, `assessmentApi`, `aiApi`
- **`lib/constants.ts`** — Shared constants
- **`app/`** — Next.js App Router pages: `auth/`, `dashboard/`, `upload/`, `students/`, `standards/`, `interventions/`, `admin/`
- **`components/`** — Organized by domain: `ai/`, `charts/`, `tables/`, `upload/`, `ui/`

### Multi-tenancy & Security

Every protected route must use the dependency injection guards from `core/dependencies.py`. All database queries **must** be scoped by `school_id` — this is the tenant isolation boundary. The middleware does not auto-apply `school_id` filtering; routers are responsible.

Student PII is **never** sent to Claude. `pseudonymize_student()` in `core/security.py` converts real student IDs to stable pseudonyms (e.g., `Student-A7F2`) before any AI API call. Analytics groups with fewer than 5 students are suppressed.

### AI / RAG Flow

1. Teacher submits a question in the chat panel
2. `ai_service.py` retrieves top-5 relevant chunks from `pgvector` via cosine similarity
3. Anonymized class stats are assembled as context (no real names/IDs)
4. Claude (`claude-3-5-sonnet-20241022`) generates either a text response or a `chart_spec` JSON
5. If `chart_spec` is returned, the backend resolves it deterministically using the analytics engine (Pandas/Plotly)

### Auth Flow

- Short-lived JWT access tokens (15 min) sent as `Authorization: Bearer`
- Rotating refresh tokens (7 days) in HttpOnly cookies
- Account lockout after 5 failed attempts (15-min lockout)
- Email verification required before login

## Key Environment Variables

| Variable | Description |
|----------|-------------|
| `POSTGRES_PASSWORD` | DB password |
| `SECRET_KEY` | 128-char hex — used for JWT signing and AES-256-GCM encryption |
| `ANTHROPIC_API_KEY` | Claude API key |
| `SMTP_*` | Email provider credentials |
| `APP_ENV` | `development` or `production` (disables OpenAPI docs in prod) |

Generate `SECRET_KEY`: `python3 -c "import secrets; print(secrets.token_hex(64))"`

## Roles

Three roles in the system, enforced via dependency guards:
- `teacher` — access to own classrooms only
- `school_admin` — access to all data within their school
- `super_admin` — cross-school access (platform admin)

## Sample Data

Seed credentials (after running `seed_db.py`):
- Admin: `admin@sampleschool.edu` / `Admin@SecurePass123!`
- Teacher: `teacher@sampleschool.edu` / `Teacher@SecurePass123!`
- School join code: `SAMPLE2026`

Sample CSVs for upload testing are in `sample_data/`.
