from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Destination, Job
from app.core.certification import certify_destination
from app.core.errors import IncuBrixError
from app.core import jobs

router = APIRouter(prefix="/api/v1", tags=["certification"])


def _cert_job(db: Session, job: Job, destination_id: str):
    destination = db.query(Destination).get(destination_id)
    run = certify_destination(db, destination)
    return {
        "certification_run_id": run.id, "ok": run.ok, "level_reached": run.level_reached,
        "evidence_path": run.evidence_path, "steps": run.steps, "error": run.error,
    }


@router.post("/destinations/{destination_id}/certify", status_code=202)
def certify(destination_id: str, idempotency_key: str = Header(default="", alias="Idempotency-Key"),
            db: Session = Depends(get_db)):
    from app.core import idempotency
    if idempotency_key:
        existing = idempotency.get_existing(db, idempotency_key, "certify")
        if existing:
            return {"job_id": existing.job_id, "status": "accepted", "note": "idempotent replay"}

    destination = db.query(Destination).get(destination_id)
    if not destination:
        raise IncuBrixError("NOT_FOUND", f"destination {destination_id} not found")

    job = jobs.create_job(db, "certify_destination", {"destination_id": destination_id})
    jobs.run_async(job.id, _cert_job, destination_id)

    if idempotency_key:
        idempotency.store_result(db, idempotency_key, "certify", {"destination_id": destination_id},
                                  {"job_id": job.id}, 202, job_id=job.id)
    return {"job_id": job.id, "status": "accepted"}
