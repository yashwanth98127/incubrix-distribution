"""Outstanding: recertification sweep demotes/excludes a destination that
fails its re-certification run, and leaves a healthy one enabled."""
from datetime import datetime, timedelta

from app.core.models import Destination
from app.core.recertification import run_recertification_sweep


def test_sweep_demotes_destination_pointed_at_dead_connector(db_session):
    stale = Destination(
        id="stale1", name="Stale Dest", url="https://stale1.example.com",
        normalized_url="stale1.example.com", platform_key="discourse",
        connector_key="discourse", enabled=True,
        last_certified_at=datetime.utcnow() - timedelta(days=40),
        instance_params={"base_url": "http://127.0.0.1:1"},  # nothing listens here -> cert must fail
    )
    db_session.add(stale)
    db_session.commit()

    run_recertification_sweep()

    db_session.refresh(stale)
    assert stale.enabled is False, "a destination that fails recertification must be auto-excluded"


def test_sweep_leaves_healthy_destination_enabled(db_session, mock_platform_server):
    healthy = Destination(
        id="healthy1", name="Healthy Dest", url="https://healthy1.example.com",
        normalized_url="healthy1.example.com", platform_key="discourse",
        connector_key="discourse", enabled=True,
        last_certified_at=datetime.utcnow() - timedelta(days=40),
    )
    db_session.add(healthy)
    db_session.commit()

    run_recertification_sweep()

    db_session.refresh(healthy)
    assert healthy.enabled is True
    assert healthy.last_certified_at > datetime.utcnow() - timedelta(minutes=5)


def test_sweep_skips_recently_certified_destination(db_session):
    fresh = Destination(
        id="fresh1", name="Fresh Dest", url="https://fresh1.example.com",
        normalized_url="fresh1.example.com", platform_key="discourse",
        connector_key="discourse", enabled=True,
        last_certified_at=datetime.utcnow() - timedelta(days=2),
        instance_params={"base_url": "http://127.0.0.1:1"},  # would fail if it were re-tested
    )
    db_session.add(fresh)
    db_session.commit()

    run_recertification_sweep()

    db_session.refresh(fresh)
    assert fresh.enabled is True, "a destination certified 2 days ago is inside the 30-day window and must not be re-tested"
