"""Outstanding: recertification scheduler. Re-tests destinations whose
last_certified_at is more than 30 days old (or never certified) and demotes
+ alerts on failure, excluding them from the live catalogue automatically."""
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.db import SessionLocal
from app.core.models import Destination
from app.core.certification import certify_destination
from app.core.logging import get_logger

logger = get_logger(component="recertification")
RECERT_WINDOW_DAYS = 30


def run_recertification_sweep():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=RECERT_WINDOW_DAYS)
        stale = db.query(Destination).filter(
            Destination.enabled == True,  # noqa: E712
            (Destination.last_certified_at == None) | (Destination.last_certified_at < cutoff),  # noqa: E711
        ).all()
        for d in stale:
            run = certify_destination(db, d)
            if not run.ok:
                d.enabled = False
                db.commit()
                logger.warning("destination_demoted_and_excluded", destination_id=d.id,
                                name=d.name, reason=run.error,
                                alert="TICKET: destination failed recertification and was auto-excluded")
            else:
                logger.info("destination_recertified", destination_id=d.id, name=d.name)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_recertification_sweep, "interval", hours=24, id="recertification_sweep")
    scheduler.start()
    return scheduler
