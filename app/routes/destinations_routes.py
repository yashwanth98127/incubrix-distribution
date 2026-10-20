"""Destination catalogue: this is the 'configuration, not code' surface
(Must-have #3). Adding a new forum/community/site of a supported connector
type is a POST here -- one row, zero new code or deploy.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.core.models import Destination
from app.core.errors import IncuBrixError

router = APIRouter(prefix="/api/v1/destinations", tags=["destinations"])


class DestinationIn(BaseModel):
    name: str
    url: str
    platform_key: str
    connector_key: str
    surface: str = "default"
    category: str = ""
    audience_tags: list[str] = []
    language: str = "en"
    geo: str = ""
    est_audience: int = 0
    rules_url: str = ""
    frequency_cap: dict = {"count": 1, "per_hours": 168}
    self_promo_allowed: bool = True
    link_policy: str = "allowed"
    disclosure_required: bool = False
    automation_allowed: bool = True
    instance_params: dict = {}


def _normalize_url(url: str) -> str:
    return url.strip().lower().rstrip("/").replace("https://", "").replace("http://", "").replace("www.", "")


@router.post("")
def create_destination(body: DestinationIn, db: Session = Depends(get_db)):
    normalized = _normalize_url(body.url)
    existing = db.query(Destination).filter(Destination.normalized_url == normalized).first()
    if existing:
        raise IncuBrixError("VALIDATION_ERROR", f"destination with this URL already exists: {existing.id}")

    dest = Destination(**body.model_dump(), normalized_url=normalized)
    db.add(dest)
    db.commit()
    db.refresh(dest)
    return {"id": dest.id, "created": True}


@router.get("")
def list_destinations(connector_key: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Destination)
    if connector_key:
        q = q.filter(Destination.connector_key == connector_key)
    rows = q.all()
    return [_serialize(d) for d in rows]


@router.get("/{destination_id}")
def get_destination(destination_id: str, db: Session = Depends(get_db)):
    d = db.query(Destination).get(destination_id)
    if not d:
        raise IncuBrixError("NOT_FOUND", f"destination {destination_id} not found")
    return _serialize(d)


def _serialize(d: Destination) -> dict:
    return {
        "id": d.id, "name": d.name, "url": d.url, "platform_key": d.platform_key,
        "connector_key": d.connector_key, "surface": d.surface, "category": d.category,
        "audience_tags": d.audience_tags, "language": d.language, "est_audience": d.est_audience,
        "rules_url": d.rules_url, "frequency_cap": d.frequency_cap,
        "self_promo_allowed": d.self_promo_allowed, "link_policy": d.link_policy,
        "disclosure_required": d.disclosure_required, "automation_allowed": d.automation_allowed,
        "relevance_score": d.relevance_score, "relevance_reason": d.relevance_reason,
        "level": d.level, "last_certified_at": d.last_certified_at.isoformat() if d.last_certified_at else None,
        "instance_params": d.instance_params, "enabled": d.enabled,
    }
