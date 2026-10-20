"""The actual /api/v1/publish flow: rules engine -> idempotency guard ->
connector.publish() -> PostRecord. This is what Must-have #4 (rules checked
before every post) and #6 (safe retries) are tested against end-to-end.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.models import Destination, PostRecord
from app.core.schemas import Rendition, DestinationRef, Connection, ValidateRequest, PublishRequest
from app.connectors.registry import get_connector
from app.core import rules
from app.core.errors import IncuBrixError


def _dest_ref(destination: Destination) -> DestinationRef:
    return DestinationRef(
        id=destination.id, name=destination.name, url=destination.url,
        platform_key=destination.platform_key, surface=destination.surface or "default",
        frequency_cap=destination.frequency_cap or {"count": 1, "per_hours": 168},
        self_promo_allowed=destination.self_promo_allowed,
        link_policy=destination.link_policy, disclosure_required=destination.disclosure_required,
        automation_allowed=destination.automation_allowed,
        instance_params=destination.instance_params or {},
    )


def publish_to_destination(db: Session, destination: Destination, rendition: Rendition,
                            idempotency_key: str, connection: Connection | None = None) -> PostRecord:
    # Safe retries: if this idempotency key already produced a PostRecord for
    # this destination, return it untouched -- never call the connector again.
    existing = (
        db.query(PostRecord)
        .filter(PostRecord.destination_id == destination.id)
        .filter(PostRecord.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing

    if not destination.enabled:
        raise IncuBrixError("CONNECTOR_DISABLED", f"destination {destination.id} is disabled")

    # Rules engine: frequency cap, self-promo, link policy, AI disclosure.
    rules.enforce(db, destination, rendition)

    connector = get_connector(destination.connector_key)
    dest_ref = _dest_ref(destination)
    connection = connection or Connection(id="svc", secret_ref="sim-key")

    v = connector.validate(ValidateRequest(rendition=rendition, destination=dest_ref, connection=connection))
    if not v.ok:
        raise IncuBrixError("DEST_SPEC_VIOLATION", "content fails destination spec", details={"violations": v.violations})

    pub = connector.publish(PublishRequest(rendition=rendition, destination=dest_ref,
                                            connection=connection, idempotency_key=idempotency_key))

    # Re-check for a race: two concurrent requests with the same key.
    existing = (
        db.query(PostRecord)
        .filter(PostRecord.destination_id == destination.id)
        .filter(PostRecord.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing

    post = PostRecord(
        destination_id=destination.id, connector_key=destination.connector_key,
        idempotency_key=idempotency_key, platform_post_id=pub.platform_post_id,
        live_url=pub.live_url, status="published", is_test_post=False,
        is_promotional=rendition.is_promotional,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post
