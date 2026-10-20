from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.core.models import Destination, Job
from app.core.schemas import Rendition, Connection
from app.core.publish_service import publish_to_destination
from app.core.errors import IncuBrixError
from app.core import jobs, idempotency

router = APIRouter(prefix="/api/v1", tags=["publish"])


class PublishIn(BaseModel):
    destination_id: str
    rendition: Rendition


def _publish_job(db: Session, job: Job, destination_id: str, rendition: dict, idem_key: str):
    destination = db.query(Destination).get(destination_id)
    if not destination:
        raise IncuBrixError("NOT_FOUND", f"destination {destination_id} not found")
    post = publish_to_destination(db, destination, Rendition(**rendition), idem_key)
    return {
        "post_id": post.id, "platform_post_id": post.platform_post_id,
        "live_url": post.live_url, "status": post.status,
    }


@router.post("/publish", status_code=202)
def publish(body: PublishIn,
            idempotency_key: str = Header(..., alias="Idempotency-Key"),
            correlation_id: str = Header(default="", alias="X-Correlation-Id"),
            db: Session = Depends(get_db)):
    existing = idempotency.get_existing(db, idempotency_key, "publish")
    if existing:
        return {"job_id": existing.job_id, "status": "accepted", "note": "idempotent replay, no new work done"}

    job = jobs.create_job(db, "publish", body.model_dump(), correlation_id=correlation_id)
    jobs.run_async(job.id, _publish_job, body.destination_id, body.rendition.model_dump(), idempotency_key)

    idempotency.store_result(db, idempotency_key, "publish", body.model_dump(), {"job_id": job.id}, 202, job_id=job.id)
    return {"job_id": job.id, "status": "accepted"}
