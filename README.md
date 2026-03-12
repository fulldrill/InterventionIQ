# Student Proficiency Insight Platform (SPIP)

> Automate weekly student math and literacy proficiency analysis aligned to Maryland Common Core Standards. Transform hours of manual CSV analysis into interactive, AI-augmented insights in minutes.

**Current proficiency gap: 4% actual → 15.9% target**

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [Problem Statement](#problem-statement)
3. [Architecture Overview](#architecture-overview)
4. [Security Overview](#security-overview)
5. [AI Architecture](#ai-architecture)
6. [Tech Stack](#tech-stack)
7. [Local Setup (Without Docker)](#local-setup-without-docker)
8. [Local Setup (With Docker)](#local-setup-with-docker)
9. [Environment Configuration](#environment-configuration)
10. [Database Migrations](#database-migrations)
11. [Seed Data](#seed-data)
12. [Email Setup](#email-setup)
13. [API Documentation](#api-documentation)
14. [Uploading Assessment Data](#uploading-assessment-data)
15. [Troubleshooting](#troubleshooting)
16. [Backup and Restore](#backup-and-restore)
17. [Deployment on Hostinger VPS](#deployment-on-hostinger-vps)
18. [Future Roadmap](#future-roadmap)

---

## Product Overview

SPIP is a multi-tenant teacher-facing web application that:

- Ingests Reveal Math assessment CSVs and question metadata files
- Maps questions to Maryland CCSS standards automatically
- Calculates proficiency by student, class, standard, and question type
- Renders interactive charts (bar, heatmap, line, scatter, stacked bar)
- Powers an AI instructional assistant using Claude API + RAG
- Anonymizes all student data before any AI API call
- Supports multiple schools, admins, and teachers with strict data isolation

---

## Problem Statement

Teachers currently spend 3-5 hours per week manually:
- Cross-referencing assessment CSV exports
- Mapping questions to CCSS standards
- Calculating averages and identifying weak standards
- Drafting intervention plans without structured data

SPIP automates this entire workflow.

---

## Architecture Overview

```
[Browser]
    ↓ HTTPS
[Nginx - Reverse Proxy + Rate Limiting + Security Headers]
    ↓
[Next.js 14 Frontend (TypeScript, TailwindCSS, shadcn/ui, Recharts)]
    ↓ REST API
[FastAPI Backend (Python 3.11)]
    ├── Authentication (Argon2id, JWT, Refresh Token Rotation)
    ├── Analytics Engine (Pandas, Plotly)
    ├── AI Service (Claude API, RAG, Anonymization)
    └── CSV Ingestion Service
    ↓
[PostgreSQL 16 + pgvector]
    ├── User & tenant data (AES-256-GCM encrypted fields)
    ├── Assessment scores & question metadata
    ├── Knowledge base embeddings (pgvector)
    └── Audit logs
```

---

## Security Overview

| Control | Implementation |
|---------|----------------|
| Password hashing | Argon2id (65536KB memory, 3 iterations) |
| Tokens | Short-lived JWT (15 min) + rotating refresh token (7 days, HttpOnly cookie) |
| Field encryption | AES-256-GCM for email, name, sensitive fields |
| Transport | TLS 1.2+ (Nginx), HSTS, secure cookies |
| Multi-tenant | school_id scoped to every query via middleware |
| AI privacy | Student PII pseudonymized before Claude API calls |
| Audit logging | All auth events and data access logged with user, timestamp, IP |
| Rate limiting | 10 req/min on login, 5 req/min on password reset |
| Account lockout | 5 failed attempts → 15-minute lockout |
| Small group suppression | Groups < 5 students masked in analytics |

FERPA alignment: Student identifiers are pseudonymized. No student names in the system. Only authorized school staff access records.

---

## AI Architecture

The AI assistant uses RAG (Retrieval-Augmented Generation):

1. Knowledge base documents (Maryland CCSS standards, teacher manuals) are chunked and embedded into pgvector
2. Teacher asks a question in the chat panel
3. Anonymized class statistics are prepared (no student names/real IDs)
4. Query is embedded and top-5 relevant knowledge chunks retrieved from pgvector
5. Claude API generates a response citing specific standards
6. If a chart is requested, Claude returns a `chart_spec` JSON — the backend resolves it deterministically

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Frontend | Next.js | 14 |
| UI | TailwindCSS + shadcn/ui | latest |
| Charts | Recharts | 2.x |
| Backend | FastAPI | 0.115 |
| Language | Python | 3.11 |
| Database | PostgreSQL | 16 |
| Vector Store | pgvector | 0.7+ |
| AI | Anthropic Claude | claude-3-5-sonnet-20241022 |
| Reverse Proxy | Nginx | alpine |
| Container | Docker + Docker Compose | latest |

---

## Local Setup (Without Docker)

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 with pgvector extension
- A running PostgreSQL database

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your local DB URL and secrets
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

---

## Local Setup (With Docker)

### Prerequisites
- Docker Desktop or Docker Engine + Docker Compose v2

### Steps

```bash
# 1. Clone repository
git clone https://github.com/your-org/spip.git
cd spip

# 2. Configure environment
cp .env.example .env
# Open .env and set all required values (see Environment Configuration below)

# 3. Build and start all services
docker compose up --build -d

# 4. Verify services are running
docker compose ps

# 5. Run database migrations
docker compose exec backend alembic upgrade head

# 6. Seed with sample data
docker compose exec backend python scripts/seed_db.py

# 7. Open the application
open http://localhost  # Nginx serves on port 80
```

---

## Environment Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `POSTGRES_PASSWORD` | Yes | Strong database password |
| `SECRET_KEY` | Yes | 128-char hex string for JWT + encryption |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `SMTP_*` | Yes | Email provider credentials |
| `APP_ENV` | Yes | `development` or `production` |

Generate a strong SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_hex(64))"
```

---

## Database Migrations

SPIP uses Alembic for database migrations.

```bash
# Apply all pending migrations
docker compose exec backend alembic upgrade head

# Create a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "describe your change"

# View migration history
docker compose exec backend alembic history

# Rollback one migration
docker compose exec backend alembic downgrade -1
```

---

## Seed Data

```bash
docker compose exec backend python scripts/seed_db.py
```

This creates:
- **School**: Sample Elementary School (Join Code: `SAMPLE2026`)
- **Admin**: admin@sampleschool.edu / Admin@SecurePass123!
- **Teacher**: teacher@sampleschool.edu / Teacher@SecurePass123!
- **Classroom**: 3rd Grade - Room 101

Then upload the sample CSVs from `sample_data/` using the teacher account.

---

## Email Setup

SPIP requires a transactional email provider for:
- Email verification on signup
- Password reset links

**Recommended providers**: Mailgun, SendGrid, or AWS SES.

In your `.env`:
```
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@mg.yourdomain.com
SMTP_PASSWORD=your-mailgun-password
EMAIL_FROM=SPIP <noreply@yourdomain.com>
```

For local development (no real emails needed), install Mailpit:
```bash
docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit
# Then set SMTP_HOST=localhost SMTP_PORT=1025
# View emails at http://localhost:8025
```

---

## API Documentation

When `APP_ENV=development`, the interactive API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

In production, these endpoints are disabled.

---

## Uploading Assessment Data

1. Log in as a teacher
2. Navigate to **Upload** page
3. Step 1: Upload your math assessment CSV (Reveal format or custom)
4. Step 2: Upload the question metadata CSV
5. Step 3 (optional): Upload literacy CSV
6. System validates both files and shows any warnings
7. Click **Process Assessment**
8. Return to Dashboard to view analytics

**Sample files** are in `sample_data/` — use these to test the upload flow.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Connection refused` on backend | Check `docker compose ps` — backend may still be starting |
| `pgvector not installed` | Run `docker compose exec db psql -U $POSTGRES_USER -c "CREATE EXTENSION vector;"` |
| Login fails immediately | Verify `SECRET_KEY` is set in `.env` |
| Email not sending | Check SMTP credentials. Use Mailpit locally for testing |
| CSV upload fails | Ensure file matches Reveal Math format. Check column headers match sample |
| AI not responding | Verify `ANTHROPIC_API_KEY` is valid and has credits |
| `alembic: command not found` | Run inside container: `docker compose exec backend alembic ...` |

---

## Backup and Restore

### Backup

```bash
# Manual backup
./scripts/backup_db.sh

# Or directly:
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB \
  | gzip > backup_$(date +%Y%m%d).sql.gz
```

### Restore

```bash
gunzip -c backup_20260301.sql.gz | \
  docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB
```

### Automated backups (cron)

```bash
# Add to crontab: daily backup at 2 AM
0 2 * * * /path/to/spip/scripts/backup_db.sh >> /var/log/spip-backup.log 2>&1
```

---

## Deployment on Hostinger VPS

### Prerequisites
- Hostinger KVM VPS running Ubuntu 22.04
- Domain name pointed at your VPS IP
- SSH access to the server

### Steps

```bash
# 1. SSH into your VPS
ssh root@your-server-ip

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# 3. Install Docker Compose
apt-get install -y docker-compose-plugin

# 4. Clone your repository
git clone https://github.com/your-org/spip.git /opt/spip
cd /opt/spip

# 5. Configure environment
cp .env.example .env
nano .env   # Set APP_ENV=production and all credentials

# 6. Get SSL certificate (Let's Encrypt)
apt-get install -y certbot
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# 7. Update nginx.conf with your domain
sed -i 's/your-domain.com/yourdomain.com/g' nginx/nginx.conf

# 8. Build and start
docker compose up --build -d

# 9. Run migrations and seed (first time only)
docker compose exec backend alembic upgrade head

# 10. Set up automatic certificate renewal
echo "0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/*.pem /opt/spip/nginx/ssl/ && docker compose restart nginx" | crontab -
```

---

## Future Roadmap

- iReady and NWEA MAP assessment CSV parsers
- Parent portal with anonymized progress reports
- Grade 4-8 CCSS standard expansion
- Benchmark comparison across classrooms
- Attendance and behavior correlation analysis
- Automated weekly email digest to teachers
- Multi-language support (Spanish)
- Offline PWA capability

---

*Built by MojiTech Solutions for Litanryan client engagement. Architecture specification in `docs/SPIP_Architecture_Specification.docx`.*
