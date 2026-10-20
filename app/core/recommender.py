"""Outstanding: given a content item, rank destinations by fit (audience
relevance, rule compatibility, past certification/post success) with a
reason for each candidate."""
from sqlalchemy.orm import Session
from app.core.models import Destination, PostRecord, CertificationRun


def _past_success_bonus(db: Session, destination_id: str) -> float:
    total = db.query(PostRecord).filter(PostRecord.destination_id == destination_id).count()
    if total == 0:
        return 0.0
    failed = db.query(PostRecord).filter(
        PostRecord.destination_id == destination_id, PostRecord.status == "failed"
    ).count()
    success_rate = 1 - (failed / total)
    return success_rate * 1.0  # up to +1.0


def rank_destinations(db: Session, content_tags: list[str], is_promotional: bool,
                       ai_generated: bool, limit: int = 10) -> list[dict]:
    destinations = db.query(Destination).filter(Destination.enabled == True).all()  # noqa: E712
    scored = []
    for d in destinations:
        if is_promotional and not d.self_promo_allowed:
            continue  # rule-incompatible: excluded, not just down-ranked
        tag_overlap = len(set(t.lower() for t in content_tags) & set(t.lower() for t in (d.audience_tags or [])))
        base = d.relevance_score or 1
        certified_bonus = 0.5 if d.last_certified_at else 0.0
        success_bonus = _past_success_bonus(db, d.id)
        score = base + tag_overlap * 0.5 + certified_bonus + success_bonus

        reasons = [f"relevance_score={base}/5 ({d.relevance_reason})"]
        if tag_overlap:
            reasons.append(f"{tag_overlap} overlapping audience tag(s)")
        if certified_bonus:
            reasons.append("destination is certified")
        if ai_generated and d.disclosure_required:
            reasons.append("requires AI disclosure (will be auto-added)")

        scored.append({
            "destination_id": d.id, "name": d.name, "connector_key": d.connector_key,
            "score": round(score, 2), "reasons": reasons,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def precision_at_k(ranked_ids: list[str], labeled_relevant_ids: set[str], k: int = 10) -> float:
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in labeled_relevant_ids)
    return round(hits / len(top_k), 3)
