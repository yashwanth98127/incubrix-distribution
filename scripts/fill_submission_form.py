#!/usr/bin/env python3
"""Fills the IncuBrix Assessment 4 Submission Form from the actual repo state
(test results, REPORT.md findings) rather than hand-typed guesses. Personal
fields (name, phone, graduation year, live links, hours spent) are left as
TODO placeholders -- only the candidate can truthfully supply those."""
import openpyxl

SRC = "/root/.claude/uploads/40b85576-cb14-54ce-9b38-3605f71a9233/142c87a5-IncuBrix_Assessment_4_Distribution_Long_Tail_Destination_Network_Submission_Form_1.xlsx"
OUT = "Assessment4_Submission_Form.xlsx"

wb = openpyxl.load_workbook(SRC)

# ---------- 1_Your_Details ----------
ws = wb["1_Your_Details"]
details = {
    "Full name": "TODO: fill in your full name",
    "Email": "jamunadevi@student.tce.edu",
    "Phone": "TODO: fill in your phone number",
    "College and degree": "Thiagarajar College of Engineering, Madurai -- B.E./B.Tech CSE",
    "Graduation year": "TODO: fill in",
    "Live demo URL": "TODO: deploy and fill in (see README Quickstart; docker compose up runs it locally meanwhile)",
    "Live demo access token or login (if protected)": "TODO: fill in if you add one",
    "Cold-start wait time (if any)": "None measured locally (in-process sqlite + mock servers start in <2s)",
    "Repository URL (private, reviewer invited)": "TODO: push this repo to a private GitHub repo and invite the reviewer username from the invitation email",
    "Demo video URL (max 8 min, unedited)": "TODO: record and fill in",
    "REPORT.md link": "REPORT.md (repo root)",
    "Compute used (laptop / cloud / GPU, with specs)": "Cloud dev container (Claude Code workspace), no GPU needed",
    "Paid services used and total cost": "None -- default path uses SIMULATION_MODE=true, AI_PROVIDER=mock, $0 total",
    "AI coding tools used (details in AI_USE.md)": "Claude (claude-sonnet-5) via Claude Code -- see AI_USE.md",
    "Approximate hours spent": "TODO: fill in your actual hours",
}
for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
    label_cell, value_cell = row[0], row[1]
    if label_cell.value in details:
        value_cell.value = details[label_cell.value]

# ---------- 2_Must_haves ----------
ws = wb["2_Must_haves"]
must_haves = {
    1: ("Yes", "app/connectors/base.py, app/connectors/*.py, app/routes/connector_routes.py ; "
               "tests/test_contract_shapes.py (6/6 connector manifests + roundtrips pass) ; "
               "test_pack/outputs/pytest_full_run.log",
        ""),
    2: ("Partial", "tests/test_certification.py (Discourse + assisted certify green) ; "
                   "test_pack/outputs/certify_discourse.result.json ; app/connectors/lemmy.py, ghost.py",
        "Discourse, Dev.to, webhook, assisted certified live via automated tests. Lemmy/Ghost connectors "
        "are fully implemented against the real Lemmy v3 / Ghost Admin APIs and docker-compose starts real "
        "local instances, but this dev sandbox's network policy blocks Docker Hub image pulls, so I could not "
        "run a live cert against them from here. See REPORT.md 'What's implemented but not live-verified'."),
    3: ("Yes", "app/routes/destinations_routes.py (POST /api/v1/destinations = one row, no code change)",
        ""),
    4: ("Yes", "app/core/rules.py ; tests/test_rules_engine.py, tests/test_hard_cases.py "
               "(frequency cap + no-promo destination both tested and blocked)",
        ""),
    5: ("Yes", "app/core/certification.py deletes test posts immediately after status check (well under "
               "10 min, see tests/test_certification.py::test_certification_cleanup_happens_quickly) ; "
               "SIMULATION_MODE=true by default, no real accounts; rate limits respected via "
               "app/connectors/http_util.py backoff",
        ""),
    6: ("Yes", "app/core/idempotency.py, app/core/publish_service.py ; "
               "tests/test_hard_cases.py::test_timeout_then_retry_with_same_idempotency_key_succeeds_once",
        ""),
    7: ("Yes", ".env.example (no real secrets committed) ; SIMULATION_MODE=true default ; "
               "app/core/logging.py never logs request bodies/headers with tokens",
        ""),
    8: ("Partial", "docker-compose.yml (app, mock-platforms, minio, real lemmy+lemmy-db, real ghost)",
        "Compose file is complete and correct by review, but could not be run end-to-end in this sandbox "
        "(Docker Hub pulls blocked by network policy here). ./scripts/run_tests.sh is the one-command path "
        "that IS verified (boots its own mock server, no docker needed, 42/42 tests pass)."),
    9: ("Partial", "openapi.yaml ; app/main.py (/health, /ready, error envelope, correlation IDs)",
        "Integration Standard code is implemented and unit/integration-tested; live demo URL not deployed "
        "yet (see 1_Your_Details)."),
}
for row in ws.iter_rows(min_row=5, max_row=ws.max_row):
    num_cell = row[0]
    if not isinstance(num_cell.value, int):
        continue
    if num_cell.value in must_haves:
        met, evidence, notes = must_haves[num_cell.value]
        row[2].value = met
        row[3].value = evidence
        row[4].value = notes

# ---------- 3_Levels ----------
ws = wb["3_Levels"]
levels = [
    ("Core", "All must-haves pass.", "Partial",
     "2 of 9 must-haves are Partial (see 2_Must_haves #2, #8) -- Lemmy/Ghost live cert and the full "
     "docker-compose stack are implemented but not run end-to-end in this sandbox."),
    ("Core", "Each Core connector passes the full certification run", "Partial",
     "4 of 6 (Discourse, Dev.to, webhook, assisted) verified live via tests/test_certification.py; "
     "Lemmy/Ghost code complete, not live-run here."),
    ("Core", "Errors from each platform are mapped to the shared error codes", "Yes",
     "app/connectors/http_util.py maps 401/422/429/503 per connector manifest error_map; "
     "tests/test_hard_cases.py covers 429/401/422 explicitly."),
    ("Advanced", "Catalogue import", "Yes",
     "app/core/catalogue.py ; tests/test_catalogue_import.py (dedupe, bad URL, missing fields all caught)."),
    ("Advanced", "Rules capture", "Partial",
     "app/routes/catalogue_routes.py propose_rules/confirm_rules + app/core/ai_adapter.py (mock, phrase-"
     "matching). Endpoint built and manually exercised; no automated test written for this specific flow."),
    ("Advanced", "Relevance score 1-5", "Yes",
     "app/core/ai_adapter.py::score_relevance ; tests/test_catalogue_import.py::"
     "test_imported_destination_gets_relevance_score."),
    ("Advanced", "Tailoring", "Yes",
     "app/core/tailoring.py ; tests/test_tailoring_and_recommender.py (word-boundary truncation, "
     "link-policy stripping, disclosure injection)."),
    ("Advanced", "Three more connectors", "No",
     "Not built -- time was spent making the required 6 Core connectors and the shared machinery "
     "(rules/certification/idempotency) solid and tested rather than adding breadth. See REPORT.md."),
    ("Outstanding", "Recommender", "Partial",
     "app/core/recommender.py ; tests/test_tailoring_and_recommender.py. Ranking + rule-exclusion tested; "
     "no real labelled set built, so precision@10 is not measured on real data (precision_at_k helper "
     "itself is unit-tested)."),
    ("Outstanding", "Metrics on >=3 connectors", "No",
     "fetch_metrics works on Discourse + Dev.to (2 connectors). Ghost's Admin API has no analytics "
     "endpoint so it returns zeros rather than fabricated numbers; Lemmy/webhook/assisted don't implement it."),
    ("Outstanding", "Recertification", "Yes",
     "app/core/recertification.py (APScheduler, 24h sweep, 30-day window) ; tests/test_recertification.py "
     "(3/3 passing: demotes failing destination, keeps healthy one, skips recently-certified one)."),
    ("Outstanding", "Real catalogue (150+)", "No",
     "Only a 7-row sample CSV (catalogue/sample_destinations.csv) to demo the import pipeline. "
     "No real destination research was done."),
]
li = iter(levels)
for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
    level_cell, item_cell = row[0], row[1]
    if level_cell.value in ("Core", "Advanced", "Outstanding"):
        try:
            _, _, done, evidence = next(li)
        except StopIteration:
            break
        row[2].value = done
        row[3].value = evidence
        row[4].value = ""

# ---------- 4_Integration ----------
ws = wb["4_Integration"]
integration = {
    "1. One-command start and test": ("Partial",
        "./scripts/run_tests.sh is verified: one command, no API keys, 42/42 tests pass "
        "(test_pack/outputs/pytest_full_run.log). docker compose up is written and reviewed but not run "
        "end-to-end here (Docker Hub pulls blocked by this sandbox's network policy)."),
    "2. Documented HTTP API": ("Yes",
        "openapi.yaml (OpenAPI 3.1, all routes under /api/v1 or /connector/v1), served live at GET "
        "/openapi.yaml and matching app/routes/*.py 1:1."),
    "3. Background jobs": ("Yes",
        "app/core/jobs.py ; POST /api/v1/publish, /certify, /catalogue/import all return 202+job_id; "
        "GET /api/v1/jobs/{id} returns status/progress/result; tested throughout test_pack and pytest suite."),
    "4. Safe retries": ("Yes",
        "Idempotency-Key header required on /api/v1/publish ; tests/test_idempotency_and_errors.py, "
        "tests/test_hard_cases.py::test_timeout_then_retry_with_same_idempotency_key_succeeds_once."),
    "5. Clear errors": ("Yes",
        "app/core/errors.py ; JSON {error:{code,message,retryable,details}}, UPPER_SNAKE_CASE codes "
        "listed in README.md ; tests/test_idempotency_and_errors.py::test_error_envelope_shape_on_not_found."),
    "6. Configuration": ("Yes",
        ".env.example lists every setting ; app/core/config.py (pydantic-settings, no hard-coded paths/keys)."),
    "7. Files in, files out": ("Partial",
        "app/core/storage.py: S3/MinIO client with local-disk fallback, used for certification evidence "
        "and assist-packs (verified via local fallback in tests, since MinIO wasn't reachable in this "
        "sandbox). Real S3/MinIO path is implemented but not exercised against a live MinIO here."),
    "8. Logs and health": ("Yes",
        "app/core/logging.py (structlog JSON, correlation_id, job_id) ; GET /health, GET /ready ; "
        "visible throughout test_pack/outputs/pytest_full_run.log."),
    "9. Output manifest": ("No",
        "Certification evidence JSON (steps, timestamps, ok/level_reached) is stored, but a formal "
        "per-result manifest (models/providers+versions, seed, cost estimate, licence/rights) as specified "
        "is not implemented yet."),
    "10. Batch runner": ("Yes",
        "scripts/batch_runner.py ; captured run in test_pack/outputs/ (_summary.json + one result file "
        "per input, including two hard cases that correctly failed as designed)."),
}
for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
    point_cell = row[0]
    if point_cell.value in integration:
        done, evidence = integration[point_cell.value]
        row[2].value = done
        row[3].value = evidence

# ---------- 5_Metrics ----------
ws = wb["5_Metrics"]
metrics = {
    "Certification": ("1 Discourse destination fully certified in the captured batch-runner demo run "
                       "(publish+confirm+status+delete, evidence stored); Discourse+assisted certification "
                       "is also exercised automatically on every test run (42/42 passing, ~1-2s per run).",
                       "Dev container, sqlite + bundled mock server, single run",
                       "test_pack/outputs/certify_discourse.result.json ; test_pack/outputs/pytest_full_run.log"),
    "Reliability": ("Publish success rate in the captured demo batch: 1/2 succeeded (the other was a "
                     "deliberate TRIGGER_429 hard case, correctly blocked -- not a real failure). "
                     "Duplicate posts under forced-timeout retry: 0 (required, verified).",
                     "Dev container, sqlite, 1 batch run + full pytest suite",
                     "test_pack/outputs/_summary.json ; tests/test_hard_cases.py::"
                     "test_timeout_then_retry_with_same_idempotency_key_succeeds_once"),
    "Rule safety": ("12 rule checks logged in the captured demo run, 1 correctly blocked (self-promotion "
                     "on a no-promo destination), 0 missed. 8 dedicated unit tests cover frequency cap, "
                     "self-promo, link policy and disclosure individually, all passing.",
                     "Dev container, sqlite, 1 batch run + tests/test_rules_engine.py (8 tests)",
                     "test_pack/outputs/_metrics_summary.json ; tests/test_rules_engine.py"),
    "Catalogue (Advanced)": ("Sample import: 7 rows in, 1 imported, 2 duplicates caught, 2 errors caught "
                              "(bad URL, missing fields). 1,000-row/5-minute benchmark not run.",
                              "Dev container, check_reachability=false",
                              "tests/test_catalogue_import.py ; catalogue/sample_destinations.csv"),
    "Recommendation (Outstanding)": ("Not measured -- no real labelled destination set has been built yet. "
                                      "The precision_at_k() helper itself is unit-tested on synthetic data.",
                                      "N/A",
                                      "tests/test_tailoring_and_recommender.py::test_precision_at_k_basic"),
    "Cost": ("$0 per 1,000 publications in the default path -- AI_PROVIDER=mock (no external call), "
              "SIMULATION_MODE=true (no paid platform APIs). No paid services were used in this submission.",
              "N/A", "SOURCES.md, REPORT.md 'Cost'"),
}
for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
    metric_cell = row[0]
    if metric_cell.value in metrics:
        val, cond, evidence = metrics[metric_cell.value]
        row[2].value = val
        row[3].value = cond
        row[4].value = evidence

# ---------- 6_Hard_cases ----------
ws = wb["6_Hard_cases"]
hard_cases = {
    1: ("Yes", "Caught and retried internally; same Idempotency-Key returns the same job and creates at "
               "most one PostRecord -- verified by forcing the mock server to drop the first call.",
        "tests/test_hard_cases.py::test_timeout_then_retry_with_same_idempotency_key_succeeds_once"),
    2: ("Yes", "429 -> PLATFORM_RATE_LIMIT (retryable=true, reset time in details); 401 -> "
               "CONNECTION_AUTH_EXPIRED; 422 -> PLATFORM_CONTENT_REJECTED. All asserted via the real HTTP "
               "contract route, not mocked at the Python level.",
        "tests/test_hard_cases.py::test_429_rate_limit_is_mapped_and_retryable, test_401_expired_token_is_mapped, "
        "test_422_content_rejected_is_mapped"),
    3: ("Yes", "Oversized title/body blocked by validate() before any platform call (DEST_SPEC_VIOLATION); "
               "manifest-driven accepted_media list rejects unsupported media types.",
        "tests/test_hard_cases.py::test_oversized_body_blocked_before_hitting_platform ; "
        "tests/test_contract_shapes.py::test_validate_rejects_oversized_title"),
    4: ("Yes", "Second post inside a 1-post/168h frequency cap is blocked with DEST_RULE_FREQUENCY_CAP; "
               "a promotional post to a self_promo_allowed=false destination is blocked with "
               "DEST_RULE_SELF_PROMO_BANNED.",
        "tests/test_hard_cases.py::test_second_post_inside_frequency_cap_is_blocked, "
        "test_promotional_post_blocked_on_no_self_promo_destination"),
    5: ("Yes", "Mock platform can rename its id field (TRIGGER_SCHEMA_DRIFT); the connector's KeyError is "
               "caught and returned as a clean JSON error, never a raw crash -- which is what makes "
               "certification fail rather than silently 'succeed'.",
        "tests/test_hard_cases.py::test_schema_drift_fails_certification_cleanly ; "
        "mocks/platform_mock/main.py (TRIGGER_SCHEMA_DRIFT)"),
    6: ("Yes", "CSV import rejects bad URLs, catches duplicates (normalised URL+platform), reports missing "
               "required fields row-by-row without aborting the whole import.",
        "tests/test_catalogue_import.py::test_import_rejects_bad_urls_and_dupes ; "
        "catalogue/sample_destinations.csv has a bad-URL and a duplicate row by design"),
    7: ("Partial", "disclosure_required destinations correctly block undisclosed AI content and pass "
                   "disclosed content (tested). Non-English community handling (language field exists on "
                   "Destination, but no language-specific validation/tailoring logic was built) and partner "
                   "permission revocation are not explicitly tested.",
        "tests/test_rules_engine.py::test_disclosure_required_blocks_undisclosed_ai_content, "
        "test_disclosure_required_allows_disclosed_ai_content"),
}
for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
    num_cell = row[0]
    if isinstance(num_cell.value, int) and num_cell.value in hard_cases:
        tested, what, evidence = hard_cases[num_cell.value]
        row[2].value = tested
        row[3].value = what
        row[4].value = evidence

# ---------- 7_Declaration ----------
ws = wb["7_Declaration"]
note = ("LEFT BLANK INTENTIONALLY -- this is your personal sworn declaration (individual work, "
        "truthfulness, rights, no hidden manual work). I (Claude) cannot sign it for you. Please read "
        "REPORT.md and AI_USE.md, confirm each statement is true for your submission, and fill in your "
        "name/date yourself before sending.")
for row in ws.iter_rows(min_row=3, max_row=ws.max_row):
    label_cell = row[0]
    if label_cell.value and ("name (as signature)" in str(label_cell.value).lower()):
        row[1].value = "TODO: sign your name here yourself"
    elif label_cell.value == "Date":
        row[1].value = "TODO: fill in"
    elif label_cell.value and label_cell.value not in ("Declaration",
            "Answer every statement. Submissions without a completed declaration are not reviewed."):
        row[1].value = "TODO: confirm (Yes) after you've read REPORT.md / AI_USE.md and verified it's true"

wb.save(OUT)
print(f"Saved {OUT}")
