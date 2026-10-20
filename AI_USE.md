# AI tool use

This submission was built with Claude (Anthropic), used as a pair-programmer inside Claude Code,
for the full engineering process: architecture, every connector, the rules engine, certification
harness, job/idempotency system, docker-compose setup, the mock-platform server, the test suite,
and this documentation.

**How it was used, concretely:**
- Writing the FastAPI service, SQLAlchemy models, and connector implementations from the brief's
  Appendix A contract.
- Writing the pytest suite (unit + integration + hard-case tests) and running it in a loop against
  a real local instance of the service to find and fix actual bugs — not just generating code
  that looked plausible. Three real defects were found and fixed this way during development:
  1. An unused duplicate FastAPI body parameter on `/api/v1/publish` that broke request parsing.
  2. A boto3 S3 client with no connect timeout, which hung a background job indefinitely when
     MinIO wasn't reachable.
  3. An HMAC signature mismatch on the webhook connector: the code signed one JSON serialization
     but sent a different one via httpx's own encoder, so every signed webhook call failed
     verification until the raw signed bytes were sent verbatim instead of re-serialized.
- Drafting this documentation set (README, REPORT, SOURCES, this file) from the actual code and
  actual test results, not a template.

**What stayed human-directed:** the system design (one Connector Runtime contract, config-driven
catalogue, rules engine as a separate pre-publish gate, certification harness with stored
evidence) follows the brief's own architecture description; the work was to implement it
correctly, verify it against real I/O, and be honest in this form about what's Core-complete
versus partial.

**Model/account used:** Claude (model identifier `claude-sonnet-5`), via Claude Code.

No other AI coding tools were used for this submission.
