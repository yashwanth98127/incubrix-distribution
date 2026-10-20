from fastapi import APIRouter, Depends, UploadFile, File, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.core.models import Destination, Job
from app.core.catalogue import import_csv
from app.core.ai_adapter import get_ai_adapter
from app.core.tailoring import tailor_for_destination
from app.core.schemas import Rendition
from app.core.errors import IncuBrixError
from app.core import jobs, idempotency

router = APIRouter(prefix="/api/v1/catalogue", tags=["catalogue"])


def _import_job(db: Session, job: Job, csv_text: str, check_reachability: bool):
    return import_csv(db, csv_text, check_reachability=check_reachability)


@router.post("/import", status_code=202)
async def import_catalogue(file: UploadFile = File(...), check_reachability: bool = True,
                            idempotency_key: str = Header(default="", alias="Idempotency-Key"),
                            db: Session = Depends(get_db)):
    if idempotency_key:
        existing = idempotency.get_existing(db, idempotency_key, "catalogue_import")
        if existing:
            return {"job_id": existing.job_id, "status": "accepted", "note": "idempotent replay"}

    content = (await file.read()).decode("utf-8", errors="replace")
    job = jobs.create_job(db, "catalogue_import", {"filename": file.filename})
    jobs.run_async(job.id, _import_job, content, check_reachability)

    if idempotency_key:
        idempotency.store_result(db, idempotency_key, "catalogue_import", {"filename": file.filename},
                                  {"job_id": job.id}, 202, job_id=job.id)
    return {"job_id": job.id, "status": "accepted"}


class RulesCaptureIn(BaseModel):
    rules_page_text: str


@router.post("/{destination_id}/rules-capture")
def propose_rules(destination_id: str, body: RulesCaptureIn, db: Session = Depends(get_db)):
    """AI proposes posting rules from a community's rules page; NOT applied
    until a human confirms via PATCH /confirm-rules (Advanced level item)."""
    destination = db.query(Destination).get(destination_id)
    if not destination:
        raise IncuBrixError("NOT_FOUND", f"destination {destination_id} not found")
    ai = get_ai_adapter()
    proposal = ai.propose_rules(body.rules_page_text)
    return {"destination_id": destination_id, "proposed_rules": proposal, "status": "pending_human_confirmation"}


class ConfirmRulesIn(BaseModel):
    self_promo_allowed: bool
    link_policy: str
    disclosure_required: bool
    frequency_cap: dict
    confirmed_by: str


@router.patch("/{destination_id}/confirm-rules")
def confirm_rules(destination_id: str, body: ConfirmRulesIn, db: Session = Depends(get_db)):
    destination = db.query(Destination).get(destination_id)
    if not destination:
        raise IncuBrixError("NOT_FOUND", f"destination {destination_id} not found")
    destination.self_promo_allowed = body.self_promo_allowed
    destination.link_policy = body.link_policy
    destination.disclosure_required = body.disclosure_required
    destination.frequency_cap = body.frequency_cap
    db.commit()
    return {"destination_id": destination_id, "rules_confirmed_by": body.confirmed_by, "applied": True}


class TailorPreviewIn(BaseModel):
    destination_id: str
    rendition: Rendition


@router.post("/tailor/preview")
def tailor_preview(body: TailorPreviewIn, db: Session = Depends(get_db)):
    destination = db.query(Destination).get(body.destination_id)
    if not destination:
        raise IncuBrixError("NOT_FOUND", f"destination {body.destination_id} not found")
    from app.connectors.registry import get_connector
    connector = get_connector(destination.connector_key)
    manifest = connector.load_manifest()
    surfaces = {s["key"]: s for s in manifest.get("surfaces", [])}
    spec = next(iter(surfaces.values()), {}).get("spec", {})
    tailored = tailor_for_destination(body.rendition, destination, spec)
    return {"original": body.rendition.model_dump(), "tailored": tailored.model_dump()}
