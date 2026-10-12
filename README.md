# PAIRWISE — AI Agents, Real Compatibility

Agentic dating platform MVP: consenting adults are represented by AI agents that analyze permitted LinkedIn + Instagram content, date other agents in multi-turn conversations, and produce explainable personalized rankings.

> **Demo data is synthetic.** Synthetic participants are never marked as verified real people. Live mode requires consented authorized profile content and an LLM API key.

## Quick start (local)

### Prerequisites

- Python 3.12+
- Node.js 20+

### 1. Backend

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
copy .env.example .env
cd backend
python -m app.seed_demo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API: http://127.0.0.1:8000  
OpenAPI: http://127.0.0.1:8000/docs

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: http://127.0.0.1:5173  
Demo: http://127.0.0.1:5173/demo

## Environment variables

See `.env.example`:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLite or Postgres URL |
| `LLM_PROVIDER` | `openai` or `none` |
| `LLM_API_KEY` | Required for live LLM calls |
| `LLM_MODEL` | Model id |
| `FRONTEND_ORIGIN` | CORS origin(s), comma-separated |
| `APP_ENV` | `development` / `production` |
| `MAX_CONCURRENT_DATES` | Dating concurrency bound |
| `DEFAULT_MAX_TURNS` | Default turns per date |

## Demo vs live

| | Demo | Live |
|--|------|------|
| Credentials | Not required | `LLM_API_KEY` required |
| Participants | 25 synthetic | Consented real submissions |
| Transcripts | Labeled demo replay | Live model responses when key set |
| Rankings | Persisted for all 24 others each | Computed from run sessions |

Seed / reseed:

```powershell
cd backend
python -m app.seed_demo
# or POST /api/demo/seed
```

## Profile ingestion

1. Validate & normalize LinkedIn/Instagram URLs (SSRF protected).
2. Attempt officially supported acquisition — currently returns `unsupported_access` for automated fetch.
3. Accept participant-authorized profile text; store provenance on `SourceRecord`.
4. Analyze with LLM (if configured) or deterministic evidence extractor.
5. Validate evidence excerpts against source text before persisting claims.

## Testing

```powershell
# Backend
cd backend
pytest -q

# Frontend unit
cd frontend
npm test

# Playwright e2e (API + frontend should be running, or use webServer)
npx playwright install chromium
npx playwright test
```

## Docker Compose

```powershell
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend: http://localhost:8000

## Database migrations

Tables are created on API startup via SQLAlchemy metadata. Alembic baseline:

```powershell
cd backend
alembic upgrade head
```

For Postgres, set `DATABASE_URL=postgresql+psycopg2://...` then run migrations / startup create.

## Deployment notes

1. Deploy backend (Fly.io, Render, Railway, etc.) with Postgres + env secrets.
2. Set `FRONTEND_ORIGIN` to the production web origin.
3. Build frontend with `VITE_API_URL` pointing at the API (or same-origin nginx proxy).
4. Seed demo only if you want public synthetic demo data.
5. Do not commit `.env`, API keys, or real participant data.
6. Publish the GitHub repo when ready — this README does not claim a public URL until you create one.

## Project layout

```
backend/app/   FastAPI, models, agents, ranking, seed
frontend/src/  React routes and UI
docs/          Architecture, API, privacy, demo script
```

## Acceptance highlights

- Working full-stack app with connected controls
- Seeded 25×24 rankings without API key
- Live LLM path when configured (no silent fake success)
- Honest source-acquisition fallback
- Automated tests included
