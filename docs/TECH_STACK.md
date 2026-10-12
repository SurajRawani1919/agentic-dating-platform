# Tech stack

## Scraping LinkedIn and Instagram

Plain HTTP (`httpx`) plus Python's standard-library `html.parser` and `json`. No headless browser, no login, no third-party key required.

| Source | Method | Extracted |
|--------|--------|-----------|
| LinkedIn | Logged-out public profile page `linkedin.com/in/<slug>` | schema.org JSON-LD (`Person`, `DiscussionForumPosting`, `Article`) + server-rendered `<section data-section>` blocks: name, headline, location, about, roles, employers, education, recent posts, articles |
| Instagram | Crawler-rendered public profile page `instagram.com/<handle>/` | Embedded JSON: name, bio, counts, verified, `is_private`, latest 12 captions with location |

Fallback chain per source: primary page → alternate rendering / `web_profile_info` endpoint → Apify actor (only if `APIFY_TOKEN` is set) → pasted profile text. Private Instagram profiles are refused outright.

Code: `backend/app/source_providers/` (`fetch.py`, `linkedin.py`, `instagram.py`).

## Backend

- Python 3.12 + FastAPI + Pydantic
- SQLAlchemy 2 + SQLite (local) / PostgreSQL-compatible URL, Alembic
- httpx LLM client (any OpenAI-compatible chat endpoint) with retries
- Rule-based analyzer and dating agent as the no-key fallback
- pytest

## Frontend

- React 18 + TypeScript + Vite, Tailwind CSS
- React Router, TanStack Query, React Hook Form + Zod
- Vitest + Testing Library, Playwright (e2e)

## Ops

- Docker + Docker Compose
- GitHub Actions CI
