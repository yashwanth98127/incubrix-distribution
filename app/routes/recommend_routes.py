from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.db import get_db
from app.core.models import Destination, PostRecord, CertificationRun, RuleViolationLog
from app.core.recommender import rank_destinations

router = APIRouter(prefix="/api/v1", tags=["recommend", "metrics"])


class RecommendIn(BaseModel):
    content_tags: list[str] = []
    is_promotional: bool = False
    ai_generated: bool = False
    limit: int = 10


@router.post("/recommend")
def recommend(body: RecommendIn, db: Session = Depends(get_db)):
    ranked = rank_destinations(db, body.content_tags, body.is_promotional, body.ai_generated, body.limit)
    return {"ranked_destinations": ranked}


@router.get("/metrics/summary")
def metrics_summary(db: Session = Depends(get_db)):
    total_dest = db.query(Destination).count()
    certified = db.query(Destination).filter(Destination.last_certified_at != None).count()  # noqa: E711
    by_connector = {}
    for row in db.query(Destination.connector_key, Destination.id).all():
        by_connector.setdefault(row[0], 0)
    cert_runs = db.query(CertificationRun).all()
    for run in cert_runs:
        by_connector.setdefault(run.connector_key, 0)
        if run.ok:
            by_connector[run.connector_key] += 1

    total_posts = db.query(PostRecord).count()
    published = db.query(PostRecord).filter(PostRecord.status == "published").count()
    from collections import Counter
    idem_counts = Counter([p.idempotency_key for p in db.query(PostRecord).all()])
    duplicate_posts = sum(1 for k, v in idem_counts.items() if v > 1)

    rule_logs = db.query(RuleViolationLog).all()
    blocked = sum(1 for r in rule_logs if r.outcome == "blocked")
    passed = sum(1 for r in rule_logs if r.outcome == "passed")

    return {
        "certification": {
            "destinations_certified_per_connector": by_connector,
            "total_destinations": total_dest,
            "total_certified": certified,
        },
        "reliability": {
            "total_publish_attempts": total_posts,
            "published": published,
            "publish_success_rate": round(published / total_posts, 3) if total_posts else None,
            "duplicate_posts_under_retry": duplicate_posts,
        },
        "rule_safety": {
            "rule_checks_run": len(rule_logs),
            "violations_blocked": blocked,
            "checks_passed": passed,
        },
    }
