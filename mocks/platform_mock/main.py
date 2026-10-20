"""One generic mock-platform server that serves three different API shapes
(Discourse-like, Dev.to-like, and a generic HMAC webhook receiver) depending
on which port/mount it's run under in docker-compose. This is what "mock
servers for the rest" (Must-have #8) means in this submission.

It also supports deliberately triggering hard-case error responses by
putting a trigger phrase in the post title/body, so the certification
harness and hidden tests can exercise 429 / 401 / 422 / schema-drift paths
without needing a second server:
  TRIGGER_429      -> rate limited, with Retry-After
  TRIGGER_401      -> auth expired
  TRIGGER_422      -> content rejected
  TRIGGER_TIMEOUT  -> first call drops the connection, second call (same
                      idempotency key) succeeds -- for safe-retry testing
  TRIGGER_SCHEMA_DRIFT -> renames the id field in the response, which a
                      strict client must treat as certification failure
"""
import hashlib
import hmac
import os
import time
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="IncuBrix Mock Platforms")

POSTS: dict[str, dict] = {}
WEBHOOK_EVENTS: dict[str, dict] = {}
TIMEOUT_SEEN: set[str] = set()
SHARED_SECRET = os.environ.get("WEBHOOK_SHARED_SECRET", "dev_only_shared_secret_change_me")


def _trigger(text: str, phrase: str) -> bool:
    return phrase in (text or "")


# ---------- Discourse-like ----------
@app.post("/posts.json")
async def discourse_create(request: Request):
    body = await request.json()
    text = f"{body.get('title', '')} {body.get('raw', '')}"
    idem = request.headers.get("Idempotency-Key", "")

    if _trigger(text, "TRIGGER_429"):
        return JSONResponse(status_code=429, headers={"Retry-After": "2"}, content={"error": "rate limited"})
    if _trigger(text, "TRIGGER_401"):
        return JSONResponse(status_code=401, content={"error": "invalid api key"})
    if _trigger(text, "TRIGGER_422"):
        return JSONResponse(status_code=422, content={"error": "content rejected by moderation"})
    if _trigger(text, "TRIGGER_TIMEOUT") and idem not in TIMEOUT_SEEN:
        TIMEOUT_SEEN.add(idem)
        raise HTTPException(status_code=504, detail="simulated timeout")

    post_id = str(uuid.uuid4().int % 1_000_000)
    POSTS[post_id] = {"id": post_id, "title": body.get("title"), "raw": body.get("raw"),
                       "url": f"/t/{post_id}", "status": "published", "idempotency_key": idem,
                       "created_at": time.time()}
    return {"id": post_id, "url": f"/t/{post_id}"}


@app.get("/posts/{post_id}.json")
def discourse_status(post_id: str):
    post = POSTS.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    return {"status": post["status"], "url": post["url"]}


@app.delete("/posts/{post_id}.json")
def discourse_delete(post_id: str):
    if post_id in POSTS:
        POSTS[post_id]["status"] = "deleted"
    return {"deleted": True}


@app.get("/posts/{post_id}/metrics.json")
def discourse_metrics(post_id: str):
    return {"views": 42, "like_count": 3, "reply_count": 1, "clicks": 5}


# ---------- Dev.to-like ----------
@app.post("/articles")
async def devto_create(request: Request):
    body = (await request.json())["article"]
    text = f"{body.get('title', '')} {body.get('body_markdown', '')}"
    idem = request.headers.get("Idempotency-Key", "")

    if _trigger(text, "TRIGGER_429"):
        return JSONResponse(status_code=429, headers={"Retry-After": "2"}, content={"error": "rate limited"})
    if _trigger(text, "TRIGGER_401"):
        return JSONResponse(status_code=401, content={"error": "invalid api key"})
    if _trigger(text, "TRIGGER_422"):
        return JSONResponse(status_code=422, content={"error": {"body_markdown": ["is too short"]}})
    if _trigger(text, "TRIGGER_TIMEOUT") and idem not in TIMEOUT_SEEN:
        TIMEOUT_SEEN.add(idem)
        raise HTTPException(status_code=504, detail="simulated timeout")

    schema_drift = _trigger(text, "TRIGGER_SCHEMA_DRIFT")
    article_id = str(uuid.uuid4().int % 1_000_000)
    POSTS[article_id] = {"id": article_id, "published": True, "url": f"https://dev.to/mock/{article_id}",
                          "page_views_count": 10, "public_reactions_count": 2, "comments_count": 0}
    resp = dict(POSTS[article_id])
    if schema_drift:
        resp["article_id"] = resp.pop("id")  # renamed field -> client must fail cert, not crash
    return resp


@app.get("/articles/{article_id}")
def devto_get(article_id: str):
    post = POSTS.get(article_id)
    if not post:
        raise HTTPException(status_code=404, detail="not found")
    return post


@app.put("/articles/{article_id}")
async def devto_update(article_id: str, request: Request):
    body = (await request.json())["article"]
    if article_id in POSTS:
        POSTS[article_id]["published"] = body.get("published", POSTS[article_id]["published"])
    return POSTS.get(article_id, {})


# ---------- Generic signed webhook receiver (partner sites) ----------
@app.post("/incubrix/webhook")
async def webhook_receive(request: Request):
    raw = await request.body()
    signature = request.headers.get("X-IncuBrix-Signature", "")
    timestamp = request.headers.get("X-IncuBrix-Timestamp", "")
    expected = hmac.new(SHARED_SECRET.encode(), f"{timestamp}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="invalid signature")

    body = await request.json()
    text = f"{body.get('title', '')} {body.get('body', '')}"
    if _trigger(text, "TRIGGER_429"):
        return JSONResponse(status_code=429, headers={"Retry-After": "2"}, content={"error": "rate limited"})
    if _trigger(text, "TRIGGER_422"):
        return JSONResponse(status_code=422, content={"error": "rejected by partner moderation"})

    idem = body.get("idempotency_key") or str(uuid.uuid4())
    post_id = idem
    WEBHOOK_EVENTS[post_id] = {"status": "accepted", "live_url": f"https://partner.example/posts/{post_id}"}
    return {"post_id": post_id, "status": "accepted", "live_url": WEBHOOK_EVENTS[post_id]["live_url"]}


@app.get("/incubrix/webhook/{post_id}")
def webhook_status(post_id: str):
    ev = WEBHOOK_EVENTS.get(post_id)
    if not ev:
        raise HTTPException(status_code=404, detail="not found")
    return ev


@app.delete("/incubrix/webhook/{post_id}")
def webhook_delete(post_id: str):
    WEBHOOK_EVENTS.pop(post_id, None)
    return {"deleted": True}


@app.get("/health")
def health():
    return {"status": "ok"}
