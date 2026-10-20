# Sources

## Libraries (all commercially-usable licenses)

| Library | License | Use |
|---|---|---|
| FastAPI | MIT | HTTP API framework |
| Uvicorn | BSD-3 | ASGI server |
| Pydantic / pydantic-settings | MIT | Request/response schemas, config |
| SQLAlchemy | MIT | ORM over sqlite (swap `DATABASE_URL` for Postgres in production) |
| httpx | BSD-3 | Outbound HTTP calls to platforms |
| PyYAML | MIT | Connector manifest parsing |
| boto3 + botocore | Apache-2.0 | S3/MinIO-compatible storage client |
| structlog | MIT/Apache-2.0 | Structured JSON logging |
| APScheduler | MIT | Recertification scheduler |
| PyJWT | MIT | Ghost Admin API JWT signing |
| pytest / pytest-asyncio | MIT | Test suite |

No GPL/AGPL dependencies are used anywhere in the default path.

## Platforms / APIs referenced

- **Discourse** — public Admin/Posts API shape (`/posts.json`), used only as a reference for
  the connector's request/response shape. Default path talks to the bundled mock server.
- **Lemmy** — public API v3 (`/api/v3/...`), MIT-licensed project. Connector talks to a real
  local Lemmy instance started by docker-compose.
- **Ghost** — public Admin API (JWT-signed), MIT-licensed project. Connector talks to a real
  local Ghost instance started by docker-compose.
- **Dev.to (forem)** — public REST API (`/api/articles`), used as a reference shape; default
  path talks to the bundled mock server (SIMULATION_MODE=false + DEVTO_API_KEY switches to
  the real hosted API at the same paths).

## AI / model usage

- **Mock AI adapter** (`app/core/ai_adapter.py`) is the default (`AI_PROVIDER=mock`): rule-based,
  deterministic, no external calls, no API key, fully commercially usable. Used for relevance
  scoring, rules-page parsing, and tailoring in the default path and in all tests/CI.
- **Optional Anthropic adapter** (`app/core/ai_adapter_anthropic.py`), used only when
  `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` is set. Not on the default path, not required
  for any must-have, level, or test to pass.

## Data

- `catalogue/sample_destinations.csv` is a small hand-written sample for demoing the catalogue
  importer; it is not a claim of a real 150-destination catalogue (see REPORT.md for what's
  implemented vs. not for the Outstanding "real catalogue" item).
- All test content (certification test posts, hard-case fixtures) is placeholder text written
  for this assessment, not scraped or copied content.
