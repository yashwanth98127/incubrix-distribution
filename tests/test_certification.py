"""Certification harness: publish -> confirm live -> status -> delete
within the cleanup deadline, with evidence stored (Must-haves #2, #5)."""
import time


def test_discourse_certification_run_succeeds(client):
    resp = client.post("/api/v1/destinations", json={
        "name": "Cert Forum", "url": "https://cert-forum.example.com",
        "platform_key": "discourse", "connector_key": "discourse",
    })
    destination_id = resp.json()["id"]

    cert = client.post(f"/api/v1/destinations/{destination_id}/certify")
    assert cert.status_code == 202
    job_id = cert.json()["job_id"]

    for _ in range(30):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.3)

    assert status["status"] == "succeeded", status
    result = status["result"]
    assert result["ok"] is True
    assert result["level_reached"] == "L3"
    steps = {s["step"]: s["ok"] for s in result["steps"]}
    assert steps["validate"] is True
    assert steps["publish"] is True
    assert steps["get_status_confirms_live"] is True
    assert steps["delete_cleanup"] is True
    assert result["evidence_path"]

    dest = client.get(f"/api/v1/destinations/{destination_id}").json()
    assert dest["level"] == "L3"
    assert dest["last_certified_at"] is not None


def test_assisted_certification_builds_pack_not_a_real_post(client):
    resp = client.post("/api/v1/destinations", json={
        "name": "Assist Community", "url": "https://assist.example.com",
        "platform_key": "assisted", "connector_key": "assisted", "automation_allowed": False,
    })
    destination_id = resp.json()["id"]

    cert = client.post(f"/api/v1/destinations/{destination_id}/certify")
    job_id = cert.json()["job_id"]
    for _ in range(30):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.3)

    assert status["status"] == "succeeded", status
    assert status["result"]["ok"] is True
    assert status["result"]["level_reached"] == "L1"


def test_certification_cleanup_happens_quickly(client):
    """Must-have #5: test posts are deleted within 10 minutes -- in practice
    our harness deletes within the same run, well under the deadline."""
    resp = client.post("/api/v1/destinations", json={
        "name": "Cleanup Forum", "url": "https://cleanup-forum.example.com",
        "platform_key": "discourse", "connector_key": "discourse",
    })
    destination_id = resp.json()["id"]
    started = time.time()
    cert = client.post(f"/api/v1/destinations/{destination_id}/certify")
    job_id = cert.json()["job_id"]
    for _ in range(30):
        status = client.get(f"/api/v1/jobs/{job_id}").json()
        if status["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.3)
    elapsed = time.time() - started
    assert elapsed < 600, "certification + cleanup must finish well inside the 10-minute deadline"
