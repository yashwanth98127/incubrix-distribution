"""Integration: every connector method, called over the real HTTP contract
route (POST /connector/v1/{connector_key}/{method}), returns the exact
Appendix A response shape. This approximates IncuBrix's own contract test
suite (Must-have #1)."""
import pytest


@pytest.mark.parametrize("connector_key", ["discourse", "devto", "webhook"])
def test_manifest_matches_appendix_a_shape(client, connector_key):
    resp = client.get(f"/connector/v1/{connector_key}/manifest")
    assert resp.status_code == 200
    m = resp.json()
    for field in ["key", "version", "tier", "auth", "surfaces", "rate_limits", "capabilities", "error_map"]:
        assert field in m, f"manifest missing '{field}'"
    assert m["key"] == connector_key


def _dest_ref(platform_key, **overrides):
    base = {
        "id": "dref1", "name": "Test dest", "url": "https://dest.example",
        "platform_key": platform_key, "surface": "default",
        "frequency_cap": {"count": 5, "per_hours": 168},
        "self_promo_allowed": True, "link_policy": "allowed",
        "disclosure_required": False, "automation_allowed": True, "instance_params": {},
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("connector_key,platform_key", [("discourse", "discourse"), ("devto", "devto"), ("webhook", "webhook")])
def test_validate_publish_status_delete_roundtrip(client, connector_key, platform_key):
    rendition = {"title": "Contract test", "body": "Contract roundtrip body", "content_type": "text"}
    destination = _dest_ref(platform_key)
    connection = {"id": "c1", "secret_ref": "sim-key"}

    v = client.post(f"/connector/v1/{connector_key}/validate",
                     json={"rendition": rendition, "destination": destination, "connection": connection})
    assert v.status_code == 200
    assert "ok" in v.json() and "violations" in v.json()
    assert v.json()["ok"] is True

    p = client.post(f"/connector/v1/{connector_key}/publish",
                     json={"rendition": rendition, "destination": destination, "connection": connection,
                           "idempotency_key": f"contract-{connector_key}"})
    assert p.status_code == 200
    body = p.json()
    assert set(body.keys()) == {"platform_post_id", "live_url", "status"}
    assert body["platform_post_id"]

    s = client.post(f"/connector/v1/{connector_key}/get_status",
                     json={"platform_post_id": body["platform_post_id"], "connection": connection})
    assert s.status_code == 200
    assert "status" in s.json()

    d = client.post(f"/connector/v1/{connector_key}/delete",
                     json={"platform_post_id": body["platform_post_id"], "connection": connection})
    assert d.status_code == 200
    assert d.json()["deleted"] is True


def test_validate_rejects_oversized_title(client):
    rendition = {"title": "x" * 999, "body": "body", "content_type": "text"}
    destination = _dest_ref("discourse")
    v = client.post("/connector/v1/discourse/validate",
                     json={"rendition": rendition, "destination": destination, "connection": {}})
    assert v.status_code == 200
    assert v.json()["ok"] is False
    assert any("title" in viol for viol in v.json()["violations"])


def test_assisted_connector_builds_pack_not_publish(client):
    rendition = {"title": "Assist me", "body": "Body text", "content_type": "text", "ai_generated": True}
    destination = _dest_ref("assisted", disclosure_required=True, automation_allowed=False)
    resp = client.post("/connector/v1/assisted/build_assist_pack",
                        json={"rendition": rendition, "destination": destination})
    assert resp.status_code == 200
    body = resp.json()
    assert body["deep_link"]
    assert body["checklist"]
    assert "AI-generated" in body["caption"] or "AI generated" in body["caption"]

    publish_attempt = client.post("/connector/v1/assisted/publish",
                                   json={"rendition": rendition, "destination": destination,
                                         "connection": {}, "idempotency_key": "x"})
    assert publish_attempt.status_code == 403
    assert publish_attempt.json()["error"]["code"] == "CONNECTOR_DISABLED"
