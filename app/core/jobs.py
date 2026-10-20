"""Minimal background-job system (Integration Standard point 3): anything
slower than BACKGROUND_THRESHOLD_SECONDS runs as a job. POST returns 202 +
job_id; GET /api/v1/jobs/{job_id} returns status/progress/result. Runs jobs
in a thread pool inside this process -- no external broker required, so
`docker compose up` with nothing else still works.
"""
import hashlib
import hmac
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.models import Job
from app.core.config import settings
from app.core.errors import IncuBrixError
from app.core.logging import get_logger

logger = get_logger(component="jobs")
_executor = ThreadPoolExecutor(max_workers=8)


def create_job(db: Session, kind: str, payload: dict, callback_url: str = "", correlation_id: str = "") -> Job:
    job = Job(kind=kind, status="queued", progress=0, payload=payload,
              callback_url=callback_url, correlation_id=correlation_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_async(job_id: str, fn, *args, **kwargs):
    _executor.submit(_run, job_id, fn, *args, **kwargs)


def _run(job_id: str, fn, *args, **kwargs):
    db = SessionLocal()
    try:
        job = db.query(Job).get(job_id)
        job.status = "running"
        job.updated_at = datetime.utcnow()
        db.commit()
        try:
            result = fn(db, job, *args, **kwargs)
            job = db.query(Job).get(job_id)
            job.status = "succeeded"
            job.progress = 100
            job.result = result
            job.updated_at = datetime.utcnow()
            db.commit()
        except IncuBrixError as e:
            job = db.query(Job).get(job_id)
            job.status = "failed"
            job.error = {**e.to_envelope()["error"], "traceback": traceback.format_exc()[-2000:]}
            job.updated_at = datetime.utcnow()
            db.commit()
            logger.warning("job_failed", job_id=job_id, code=e.code, error=e.message)
        except Exception as e:
            job = db.query(Job).get(job_id)
            job.status = "failed"
            job.error = {"code": "INTERNAL_ERROR", "message": str(e), "retryable": True,
                         "details": {}, "traceback": traceback.format_exc()[-2000:]}
            job.updated_at = datetime.utcnow()
            db.commit()
            logger.error("job_failed", job_id=job_id, error=str(e))
        if job.callback_url:
            _send_callback(job)
    finally:
        db.close()


def _send_callback(job: Job):
    body = json.dumps({
        "job_id": job.id, "status": job.status, "result": job.result, "error": job.error,
    }, default=str).encode()
    signature = hmac.new(settings.WEBHOOK_SHARED_SECRET.encode(), body, hashlib.sha256).hexdigest()
    try:
        httpx.post(job.callback_url, content=body,
                   headers={"Content-Type": "application/json", "X-IncuBrix-Signature": signature},
                   timeout=10.0)
    except Exception as e:
        logger.warning("job_callback_failed", job_id=job.id, error=str(e))


def set_progress(db: Session, job: Job, progress: int):
    job.progress = progress
    job.updated_at = datetime.utcnow()
    db.commit()
