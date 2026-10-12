# PAIRWISE — an agentic dating site

Every person is represented by an agent. The agent reads that person's **public LinkedIn** and **public Instagram** — the only two sources — builds a profile page, dates every other agent on the person's behalf, and ranks who fits them best.

## Overall explanation (200 characters)

> Paste a LinkedIn + public Instagram link. An agent reads both, profiles the person's needs, hobbies and interests, dates every other agent on their behalf, and ranks who fits each person best.

## How it works

```
LinkedIn public profile  +  Instagram public profile
                 ↓
   The agent reads both and analyzes the person
                 ↓
   Profile page — needs · hobbies · interests · values · personality
                 ↓
   The agents date — every agent dates every other agent, one-to-one
                 ↓
   Ranking — each person's own list of who fits them best
```

1. **Links in.** `POST /api/participants` takes the two links. Both pages are read live; the name is taken from the profiles.
2. **Reading.** Each profile becomes plain text (headline, about, roles, education, recent posts / bio, latest captions). The profile page shows exactly what the agent read.
3. **Analysis.** The agent extracts needs, hobbies, interests, values, personality, lifestyle and communication style. Every claim carries a verbatim quote from the source, and claims whose quote is not in the source are dropped.
4. **Dating.** Each agent knows only its own person plus what is said in the conversation — it never sees the other profile. A date is a multi-turn exchange: open, react, share, probe a need, close with an honest read.
5. **Verdicts.** After a date, both agents privately score how well the other person fits *their* person (needs met, needs unmet, friction).
6. **Ranking.** Rankings are personal and can be asymmetric: 50% own agent's verdict, 30% mutual session score, 20% the other agent's verdict.

## Technical section — how Instagram and LinkedIn are scraped

Plain HTTP with `httpx` and Python's standard-library parsers; no headless browser and no login.

| Source | Primary method | What is extracted | Fallbacks |
|--------|----------------|-------------------|-----------|
| **LinkedIn** | `GET linkedin.com/in/<slug>` — the logged-out public profile page | schema.org **JSON-LD** graph (`Person`: name, about, job titles, employers, schools, location; `DiscussionForumPosting`: recent posts; `Article`: published articles) plus server-rendered `<section data-section>` blocks (experience, education, volunteering, languages, honors) parsed with `html.parser` | crawler-rendered page, then an Apify actor if `APIFY_TOKEN` is set |
| **Instagram** | `GET instagram.com/<handle>/` as a search crawler — Instagram pre-renders public profiles | embedded `application/json` payload: full name, bio, follower counts, verified flag, `is_private`, and the latest 12 post captions (with location) | `web_profile_info` JSON endpoint, then Apify `instagram-profile-scraper` if `APIFY_TOKEN` is set |

- **Private Instagram profiles are refused** (`is_private`), per the brief.
- **Same-person check:** the name on the LinkedIn profile is compared with the Instagram name/handle.
- **SSRF-safe:** only `linkedin.com/in/…` and `instagram.com/…` URLs are accepted and redirects may not leave the platform host.
- **Datacenter IPs** are often blocked by both platforms. For a hosted deployment set `APIFY_TOKEN` or `SCRAPER_PROXY`, or build the example locally and ship it with the snapshot (below).

Code: [backend/app/source_providers/](backend/app/source_providers/).

**Stack:** FastAPI · SQLAlchemy · SQLite/Postgres · httpx — React 18 · TypeScript · Vite · Tailwind · TanStack Query. Agents use any OpenAI-compatible chat model when `LLM_API_KEY` is set; without a key, built-in rule-based agents analyze and date instead, and every message and profile is labeled with the engine that produced it.

## Quick start

```powershell
# Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — **Add people** to paste links, **Demo** for the finished example.

Copy `.env.example` to `.env` (repo root) to set an LLM key:

| Variable | Purpose |
|----------|---------|
| `LLM_API_KEY`, `LLM_PROVIDER=openai`, `LLM_MODEL`, `LLM_BASE_URL` | LLM agents (any OpenAI-compatible endpoint) |
| `APIFY_TOKEN` | Optional scraping fallback for hosted deployments |
| `SCRAPER_PROXY` | Optional HTTP proxy for profile reads |
| `DEMO_VIDEO_URL` | YouTube walkthrough, embedded on the Demo page |
| `DATABASE_URL` | SQLite (default) or Postgres |
| `FRONTEND_ORIGIN` | CORS origin(s), comma-separated |

## Building the 25-person example

```powershell
cd backend
python -m app.cohort ingest people.csv   # one "linkedin_url,instagram_url" per line
python -m app.cohort date                # every agent dates every other agent, then rank
python -m app.cohort export              # writes demo_snapshot.json
```

On startup the API loads `demo_snapshot.json` into an empty database, so a deployed site opens with the finished example already run. `/demo` always shows the largest finished run over real people; a clearly labeled synthetic sample is shown only while no such run exists.

## Testing

```powershell
cd backend;  pytest -q        # parsers, analysis, agents, ranking, snapshot
cd frontend; npm test; npm run build
```

Tests never touch LinkedIn or Instagram — the parsers run against page fixtures.

## Deployment

1. Deploy the backend (Render, Railway, Fly.io…) with the env vars above; commit `backend/demo_snapshot.json` so the example ships with it.
2. Build the frontend with `VITE_API_URL` pointing at the API, or use `docker compose up --build` (frontend on :8080, API on :8000).
3. Set `FRONTEND_ORIGIN` to the web origin.

## Privacy

Only public profile pages are read, private Instagram accounts are refused, sensitive traits (orientation, ethnicity, religion, health, politics) are never inferred, and any person can be removed with one click on their profile page (`DELETE /api/participants/{id}`). See [docs/PRIVACY.md](docs/PRIVACY.md).
