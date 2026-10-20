"""Safe retries: an Idempotency-Key on a POST must never do the work twice
(Integration Standard point 4, Must-have #6)."""
import hashlib
import json
from sqlalchemy.orm import Session

from app.core.models import IdempotencyRecord


def _hash_body(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def get_existing(db: Session, key: str, route: str):
    if not key:
        return None
    rec = db.query(IdempotencyRecord).filter_by(key=key, route=route).first()
    return rec


def store_result(db: Session, key: str, route: str, body: dict, response_body: dict, status_code: int, job_id: str = ""):
    if not key:
        return
    rec = IdempotencyRecord(
        key=key,
        route=route,
        request_hash=_hash_body(body),
        job_id=job_id,
        response_body=response_body,
        status_code=status_code,
    )
    db.merge(rec)
    db.commit()
