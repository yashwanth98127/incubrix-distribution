# IncuBrix Distribution: Long-Tail Destination Network

Connector service for forums, developer blogs, newsletters and partner sites, built to the
IncuBrix connector contract (Appendix A) and Integration Standard.

## What this is

A single FastAPI service that:
- Exposes every connector method over HTTP exactly per the contract: `POST /connector/v1/{connector_key}/{method}`
- Runs a posting-rules engine (frequency cap, self-promotion, link policy, AI disclosure) before every publish
- Runs a certification harness (publish → confirm live → status → delete, with stored evidence)
- Manages a destination catalogue as **configuration, not code** (new forum = one row)
- Does background jobs, idempotent retries, structured errors and logs per the Integration Standard

Six connectors ship: **Discourse, Lemmy, Dev.to, Ghost, a generic HMAC-signed webhook (partner
sites), and an assisted connector** (builds a ready-to-post pack for communities where
automation isn't allowed).

## Architecture

```
                        ┌─────────────────────────────┐
  POST /api/v1/publish  │                             │  POST /connector/v1/{key}/{method}
 ─────────────────────► │   FastAPI app (app/main.py) │ ◄──────────────────────────────────
  (rules + idempotency) │                             │   (raw Appendix A contract, used
                         ├─────────────┬───────────────┤    directly by IncuBrix's own
                         │ rules.py    │ connectors/    │    Connector Runtime)
                         │ (frequency, │  discourse.py  │
                         │  self-promo,│  lemmy.py      │───► real local Lemmy (docker)
                         │  link,      │  devto.py      │───► mock platform server
                         │  disclosure)│  ghost.py      │───► real local Ghost (docker)
                         │             │  webhook.py    │───► partner site (HMAC-signed)
                         │             │  assisted.py   │───► no network call; builds a pack
                         ├─────────────┴───────────────┤
                         │ certification.py  (publish → confirm → status → delete, evidence)
                         │ jobs.py            (background jobs, 202 + job_id)
                         │ idempotency.py     (same key never does the work twice)
                         │ storage.py         (S3/MinIO, local-disk fallback)
                         │ catalogue.py       (CSV import, dedupe, reachability, relevance)
                         │ recommender.py     (rank destinations for a content item)
                         │ recertification.py (scheduler: re-test destinations before 30 days)
                         └──────────────┬───────────────┘
                                        │ SQLAlchemy / sqlite (swap DATABASE_URL for Postgres)
                               destinations, connections, post_records,
                               certification_runs, jobs, idempotency_records
```

One output field, end to end — tracing `platform_post_id`: a client calls `POST /api/v1/publish`
→ `publish_service.py` runs the rules engine, then calls the connector's `publish()` → the
connector calls the real/mock platform and gets back `{platform_post_id, live_url, status}` →
that's stored on a `PostRecord` row → the job result returned from `GET /api/v1/jobs/{id}`
echoes `platform_post_id` straight from that row. Nothing re-derives or guesses it.

## Quickstart

```bash
cp .env.example .env
docker compose up          # app + mock platforms + MinIO + a real local Lemmy + a real local Ghost
curl http://localhost:8080/health
```

No API keys are required — `SIMULATION_MODE=true` by default, connectors for Discourse/Dev.to/the
webhook talk to the bundled mock platform server, and Lemmy/Ghost talk to the real local instances
docker-compose starts for you.

### Run the tests (one command, no API keys)

```bash
./scripts/run_tests.sh
```

This boots its own instance of the mock platform server, runs unit + integration + end-to-end
tests (42 tests: rules engine, idempotency, certification, hard cases, catalogue import,
recommender, recertification) against a fresh sqlite DB, and tears everything down. See
`test_pack/outputs/pytest_full_run.log` for a captured run.

### Batch runner (Integration Standard point 10)

```bash
python scripts/batch_runner.py --input test_pack/inputs --output test_pack/outputs --base-url http://localhost:8080
```

Runs every `*.json` spec in the input folder against the live API and writes one result file +
a `_summary.json` to the output folder. See `test_pack/outputs/` for a captured run.

## Configuration

Everything is environment-driven (`.env.example` lists every setting; Integration Standard point
6) — no hard-coded paths, keys, or model names anywhere in `app/`.

| Variable | Purpose |
|---|---|
| `SIMULATION_MODE` | `true` (default): no real accounts needed, uses mocks + local instances |
| `DATABASE_URL` | sqlite by default; point at Postgres for production |
| `S3_ENDPOINT_URL` etc. | MinIO/S3-compatible storage for evidence, assist-packs, catalogue reports |
| `LEMMY_BASE_URL` / `GHOST_BASE_URL` | real local instances from docker-compose |
| `WEBHOOK_SHARED_SECRET` | HMAC secret for the generic webhook connector |
| `AI_PROVIDER` | `mock` (default, no key) or `anthropic` |

## Error codes (Integration Standard point 5)

All errors are JSON: `{"error": {"code", "message", "retryable", "details"}}`. Codes (see
`app/core/errors.py`):

| Code | Retryable | Meaning |
|---|---|---|
| `DEST_SPEC_VIOLATION` | No | Content breaks the destination's format limits |
| `DEST_RULE_FREQUENCY_CAP` | Later | Frequency cap reached |
| `DEST_RULE_SELF_PROMO_BANNED` | No | Destination bans self-promotion |
| `DEST_RULE_LINK_POLICY` | No | Content violates the destination's link policy |
| `DEST_RULE_DISCLOSURE_REQUIRED` | No | AI-content disclosure missing |
| `CONNECTION_AUTH_EXPIRED` | After reconnect | Token expired/revoked |
| `PLATFORM_RATE_LIMIT` | Yes | Back off using the platform's reset time |
| `PLATFORM_QUOTA_EXHAUSTED` | Next window | Daily quota used up |
| `PLATFORM_CONTENT_REJECTED` | No | Platform refused the content |
| `PLATFORM_UNAVAILABLE` | Yes | Retried internally up to 5x, then surfaced |
| `CONNECTOR_DISABLED` | No | Kill switch / assisted connector can't auto-publish |
| `CERTIFICATION_FAILED` | No | Certification run did not pass |
| `NOT_FOUND` / `VALIDATION_ERROR` / `INTERNAL_ERROR` | varies | Standard cases |

## Endpoints

See `openapi.yaml` (served live at `GET /openapi.yaml`, matches the running service) and the
interactive docs at `GET /docs`. Everything IncuBrix-facing is under `/api/v1/`; the raw connector
contract is under `/connector/v1/{connector_key}/{method}`.

## What's Core-complete vs. partial

See `REPORT.md` for the honest breakdown of must-haves, levels, and the Integration Standard —
including what's verified by an automated, passing test versus implemented-but-not-live-verified
(mainly: Lemmy/Ghost against *real* local instances, which this development environment could not
pull Docker images for — see REPORT.md for why and how to verify it yourself in one command).
