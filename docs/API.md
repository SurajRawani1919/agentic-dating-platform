# API

OpenAPI docs are available at `/docs` when the API is running.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health, version, LLM configured flag |
| GET | `/api/settings` | Non-secret runtime settings |
| GET | `/api/participants` | Paginated participant list |
| POST | `/api/participants` | Read both links, create the person, run the analysis |
| POST | `/api/participants/{id}/refresh` | Re-read both profiles and re-analyze |
| GET | `/api/runs` | Recent dating runs |
| GET | `/api/participants/{id}` | Participant detail + sources |
| DELETE | `/api/participants/{id}` | Delete participant and related data |
| POST | `/api/participants/{id}/analyze` | Run profile analysis |
| GET | `/api/participants/{id}/analysis` | Latest analysis |
| POST | `/api/runs` | Create dating run + pair sessions |
| GET | `/api/runs/{id}` | Run status / progress |
| POST | `/api/runs/{id}/start` | Start background orchestration |
| POST | `/api/runs/{id}/resume` | Resume unfinished sessions |
| POST | `/api/runs/{id}/cancel` | Cancel in-flight run |
| GET | `/api/runs/{id}/sessions` | Sessions for a run |
| GET | `/api/dates/{id}` | Date session detail |
| GET | `/api/dates/{id}/transcript` | Messages + session |
| POST | `/api/dates/{id}/evaluate` | Recompute evaluation scores |
| GET | `/api/rankings/{participant_id}` | Personalized rankings |
| GET | `/api/demo` | The finished example: largest completed run over real people |
| GET | `/api/demo/{run_id}` | Demo run detail |
| POST | `/api/demo/seed` | Reseed synthetic demo |

Errors return JSON `{ "detail": "..." }` with appropriate HTTP status codes.
