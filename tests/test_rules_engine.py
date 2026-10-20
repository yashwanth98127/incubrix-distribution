"""Unit tests for the posting-rules engine (Must-have #4)."""
from app.core import rules
from app.core.models import Destination
from app.core.schemas import Rendition


def make_dest(**overrides):
    defaults = dict(
        id="d1", name="Test", url="https://x.example", normalized_url="x.example",
        platform_key="discourse", connector_key="discourse", frequency_cap={"count": 1, "per_hours": 168},
        self_promo_allowed=True, link_policy="allowed", disclosure_required=False,
    )
    defaults.update(overrides)
    return Destination(**defaults)


def test_self_promo_blocks_promotional_content():
    dest = make_dest(self_promo_allowed=False)
    result = rules.check_self_promo(dest, is_promotional=True)
    assert result.ok is False
    assert "self-promotion" in result.reason


def test_self_promo_allows_non_promotional_content():
    dest = make_dest(self_promo_allowed=False)
    result = rules.check_self_promo(dest, is_promotional=False)
    assert result.ok is True


def test_link_policy_none_blocks_any_link():
    dest = make_dest(link_policy="none")
    result = rules.check_link_policy(dest, "check out https://example.com", None)
    assert result.ok is False


def test_link_policy_one_link_blocks_multiple():
    dest = make_dest(link_policy="one_link")
    result = rules.check_link_policy(dest, "see https://a.com and https://b.com", None)
    assert result.ok is False


def test_link_policy_one_link_allows_single():
    dest = make_dest(link_policy="one_link")
    result = rules.check_link_policy(dest, "see https://a.com", None)
    assert result.ok is True


def test_disclosure_required_blocks_undisclosed_ai_content():
    dest = make_dest(disclosure_required=True)
    result = rules.check_disclosure(dest, ai_generated=True, body="just a normal post")
    assert result.ok is False


def test_disclosure_required_allows_disclosed_ai_content():
    dest = make_dest(disclosure_required=True)
    result = rules.check_disclosure(dest, ai_generated=True, body="this is AI-generated content")
    assert result.ok is True


def test_disclosure_not_required_for_human_content():
    dest = make_dest(disclosure_required=True)
    result = rules.check_disclosure(dest, ai_generated=False, body="a human wrote this")
    assert result.ok is True


def test_frequency_cap_blocks_second_post_in_window(db_session):
    from app.core.models import PostRecord
    dest = make_dest(id="d_freq", frequency_cap={"count": 1, "per_hours": 168})
    db_session.add(dest)
    db_session.commit()
    db_session.add(PostRecord(destination_id=dest.id, connector_key="discourse",
                               idempotency_key="k1", status="published"))
    db_session.commit()

    result = rules.check_frequency_cap(db_session, dest)
    assert result.ok is False
    assert "frequency cap" in result.reason


def test_frequency_cap_allows_first_post(db_session):
    dest = make_dest(id="d_freq2", frequency_cap={"count": 1, "per_hours": 168})
    db_session.add(dest)
    db_session.commit()
    result = rules.check_frequency_cap(db_session, dest)
    assert result.ok is True
