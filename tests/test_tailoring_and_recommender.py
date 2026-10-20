from app.core.tailoring import truncate_at_word_boundary
from app.core.recommender import precision_at_k


def test_truncate_at_word_boundary_does_not_cut_mid_word():
    text = "The quick brown fox jumps over the lazy dog"
    out = truncate_at_word_boundary(text, 20)
    assert len(out) <= 21  # ellipsis char
    assert not out.rstrip("…").endswith(("jum", "jump"))


def test_truncate_noop_when_under_limit():
    text = "short text"
    assert truncate_at_word_boundary(text, 100) == text


def test_precision_at_k_basic():
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c", "e", "z"}
    assert precision_at_k(ranked, relevant, k=5) == 0.6


def test_recommend_excludes_promo_banned_destinations(client):
    client.post("/api/v1/destinations", json={
        "name": "No Promo Forum", "url": "https://nopromo.example.com",
        "platform_key": "discourse", "connector_key": "discourse",
        "self_promo_allowed": False, "audience_tags": ["ai"],
    })
    client.post("/api/v1/destinations", json={
        "name": "Promo OK Forum", "url": "https://promook.example.com",
        "platform_key": "discourse", "connector_key": "discourse",
        "self_promo_allowed": True, "audience_tags": ["ai"],
    })
    resp = client.post("/api/v1/recommend", json={"content_tags": ["ai"], "is_promotional": True})
    names = [r["name"] for r in resp.json()["ranked_destinations"]]
    assert "No Promo Forum" not in names
    assert "Promo OK Forum" in names
