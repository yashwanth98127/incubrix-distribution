"""Integration Standard point 4 (safe retries) and point 5 (clear errors)."""


def test_idempotent_publish_returns_same_job_and_one_post(client):
    dest = client.post("/api/v1/destinations", json={
        "name": "Idem Dest", "url": "https://idem-dest.example.com",
        "platform_key": "discourse", "connector_key": "discourse",
        "frequency_cap": {"count": 10, "per_hours": 168},
    }).json()
    destination_id = dest["id"]

    body = {"destination_id": destination_id,
            "rendition": {"title": "Idempotent post", "body": "same body", "content_type": "text"}}
    r1 = client.post("/api/v1/publish", headers={"Idempotency-Key": "same-key-1"}, json=body)
    r2 = client.post("/api/v1/publish", headers={"Idempotency-Key": "same-key-1"}, json=body)
    assert r1.json()["job_id"] == r2.json()["job_id"]

    import time
    time.sleep(1.0)
    from app.core.db import SessionLocal
    from app.core.models import PostRecord
    db = SessionLocal()
    count = db.query(PostRecord).filter(PostRecord.idempotency_key == "same-key-1").count()
    db.close()
    assert count == 1


def test_missing_idempotency_key_is_rejected(client):
    resp = client.post("/api/v1/publish", json={
        "destination_id": "whatever",
        "rendition": {"title": "t", "body": "b", "content_type": "text"},
    })
    assert resp.status_code == 422  # FastAPI header validation error


def test_error_envelope_shape_on_not_found(client):
    resp = client.get("/api/v1/destinations/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    err = body["error"]
    assert set(["code", "message", "retryable", "details"]).issubset(err.keys())
    assert err["code"] == err["code"].upper()
    assert "_" in err["code"] or err["code"].isupper()


def test_health_and_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    ready = client.get("/ready").json()
    assert ready["status"] == "ready"
    assert ready["db_ok"] is True
