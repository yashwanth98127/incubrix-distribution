# REPORT — IncuBrix Distribution: Long-Tail Destination Network

## Approach and why

The brief's own key idea — "one connector, many destinations" — is the whole design. A
`Destination` is a database row (name, URL, connector_key, rules, instance_params); a `Connector`
is stateless code that implements seven contract methods against the Appendix A shape. Adding
forum #41 is a `POST /api/v1/destinations` call, never a deploy. I built the rules engine as a
**separate gate in front of** `connector.publish()`, not inside each connector, so frequency cap /
self-promo / link policy / AI-disclosure are enforced identically for every connector and tested
once, not six times differently. The certification harness is a thin orchestrator that calls the
same `validate → publish → get_status → delete` sequence any client would, so certifying a
destination exercises exactly the code path real publishing uses — no separate "demo path."

I considered making each connector own its own idempotency/retry logic; I rejected that because
the brief's hard cases (timeout+retry, 429 backoff) are cross-cutting, and testing them once in
`idempotency.py` / `http_util.py` is far more reliable than six near-duplicate implementations.

## What works (verified by a passing automated test — see `test_pack/outputs/pytest_full_run.log`, 42/42 passing)

- **Connector contract** over HTTP exactly per Appendix A, for all 6 connectors (manifest shape,
  validate/publish/get_status/delete, error-code mapping) — `tests/test_contract_shapes.py`.
- **Rules engine**: frequency cap, self-promotion, link policy, AI-disclosure, each with its own
  unit test and an end-to-end test through `/api/v1/publish` — `tests/test_rules_engine.py`,
  `tests/test_hard_cases.py`.
- **Certification harness**: full publish→confirm→status→delete run with stored evidence, for the
  Discourse (mock) and assisted connectors — `tests/test_certification.py`.
- **Safe retries**: same `Idempotency-Key` returns the same job and never creates a second
  `PostRecord`, verified under a forced-timeout hard case — `tests/test_hard_cases.py`,
  `tests/test_idempotency_and_errors.py`.
- **Hard cases**: 429 with backoff, expired token (401), content rejected (422), timeout+retry,
  oversized content blocked pre-platform, promotional content blocked on a no-promo destination,
  second post inside a frequency cap blocked, and a platform schema-drift case that must fail
  cleanly rather than crash — all in `tests/test_hard_cases.py`.
- **Catalogue import (Advanced)**: validates, de-duplicates (normalised URL + platform), checks
  reachability, scores relevance, with a row-by-row error report —
  `tests/test_catalogue_import.py`.
- **Relevance scoring & tailoring (Advanced)**: truncation at a word boundary, forum discussion
  framing, link-policy stripping, disclosure injection — `tests/test_tailoring_and_recommender.py`.
- **Recommender (Outstanding)**: ranks destinations by relevance/tags/certification/past success,
  excludes rule-incompatible destinations outright, `precision_at_k` helper for labelled-set
  scoring — `tests/test_tailoring_and_recommender.py`.
- **Recertification scheduler (Outstanding)**: a destination that fails re-certification is
  auto-demoted and disabled; a healthy one is re-certified and re-enabled; a recently-certified one
  is left alone — `tests/test_recertification.py`.
- **Integration Standard**: background jobs (202+job_id, poll by id), Idempotency-Key on every
  POST, JSON error envelope with UPPER_SNAKE_CASE codes, env-driven config, S3/MinIO storage with
  local-disk fallback, structured JSON logs with correlation IDs, `/health` + `/ready`, `openapi.yaml`
  served live and matching the running routes, and the batch runner —
  `tests/test_idempotency_and_errors.py` plus a captured `scripts/batch_runner.py` run in
  `test_pack/outputs/`.

Three real bugs were found and fixed by actually running this (not just writing it) — see
`AI_USE.md` for the specifics (a broken request body param, a hung S3 client with no timeout, and
an HMAC signature mismatch between what was signed and what was sent).

## What's implemented but not live-verified, and why

- **Lemmy and Ghost connectors** are fully implemented against the real public Lemmy v3 API and
  Ghost Admin API (login/JWT, create/status/delete). `docker-compose.yml` starts real local Lemmy
  and Ghost containers exactly as Must-have #8 asks. **This development sandbox's network
  allowlist blocks pulling images from Docker Hub** (`docker compose build` fails resolving
  `python:3.11-slim` / the Lemmy/Ghost images with a 403), so I could not run a live certification
  against real Lemmy/Ghost containers from here. The connector code, request shapes, and the
  compose file are complete and were reviewed carefully, but per the brief's own honesty rule
  ("mark something No or Partial and explain why"), I'm marking this **Partial** rather than
  claiming a run I couldn't perform. Run `docker compose up` on a machine with normal Docker Hub
  access and `POST /api/v1/destinations/{id}/certify` against a Lemmy or Ghost destination to
  verify directly — the code path is identical to the Discourse/Dev.to runs that are verified.
- **`fetch_metrics`** genuinely works on Discourse and Dev.to (mock-backed). Ghost's Admin API has
  no analytics endpoint, so that connector returns zeros rather than fabricating numbers — the
  Outstanding bar ("works on at least three connectors") is **not met**; it's 2 of 6, honestly.

## What's not implemented

- **Three more Advanced connectors** (Hashnode / Slack / newsletter / MRSS / PeerTube) — not
  built. Time was spent making the Core six connectors and the rules/certification/idempotency
  machinery solid and genuinely tested rather than adding breadth with shallow coverage.
- **Real 150-destination catalogue** (Outstanding) — only a 7-row sample CSV
  (`catalogue/sample_destinations.csv`) exists, to demonstrate the import pipeline. No real
  destination research was done.
- **1,000-row / 5-minute catalogue benchmark** — the import pipeline is built for concurrent
  reachability checks (`ThreadPoolExecutor`, 32 workers) and should clear this comfortably, but it
  has not been benchmarked at that scale.
- **Live demo URL** — not deployed yet; this submission currently ships as a repository + Docker
  Compose stack. (See README Quickstart — `docker compose up` is the equivalent one-command
  start the brief asks the Integration Standard to guarantee.)

## Cost

Default path cost is **$0 per 1,000 publications** — `AI_PROVIDER=mock` (rule-based, deterministic,
no external call) is what the rules-capture and relevance-scoring steps use by default, and all
six connectors talk to free local/mock infrastructure in `SIMULATION_MODE`. The optional Anthropic
adapter (`app/core/ai_adapter_anthropic.py`) is off by default and was not exercised or costed in
this submission.

## Numbers measured

See the Metrics tab of the Submission Form and `test_pack/outputs/_metrics_summary.json` for a
captured run: certification succeeded for the Discourse connector in the batch-runner demo;
publish success rate and duplicate-post count (0, as required) are computed live by
`GET /api/v1/metrics/summary` from real `PostRecord`/`CertificationRun` rows, not hand-entered.

## What I'd do next

1. Get this running against real Docker Hub access and certify Lemmy + Ghost for real (the code
   is written; it needs infrastructure this sandbox didn't have).
2. Add the three remaining Advanced connectors, reusing the same `Connector` base class.
3. Wire `fetch_metrics` for Lemmy (community stats) and the webhook connector (if the partner
   exposes one) to hit the Outstanding "three connectors" bar honestly.
4. Build the real 150-destination catalogue and a small labelled set to score the recommender's
   precision@10 properly, rather than the synthetic example in the tests.
5. Deploy a real live demo URL with an access token and a rate limit, per the submission checklist.
