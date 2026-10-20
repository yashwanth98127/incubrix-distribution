"""Posting-rules engine. Runs before every publish() call. Checks frequency
cap, self-promotion policy, link policy and AI-disclosure, and blocks or
reschedules with a clear reason (Must-have #4).
"""
from datetime import datetime, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.models import Destination, PostRecord, RuleViolationLog
from app.core.errors import IncuBrixError


@dataclass
class RuleCheckResult:
    ok: bool
    reason: str = ""
    retry_after: datetime | None = None


def _log(db: Session, destination_id: str, rule: str, outcome: str, reason: str):
    db.add(RuleViolationLog(destination_id=destination_id, rule=rule, outcome=outcome, reason=reason))
    db.commit()


def check_frequency_cap(db: Session, destination: Destination) -> RuleCheckResult:
    cap = destination.frequency_cap or {"count": 1, "per_hours": 168}
    window_start = datetime.utcnow() - timedelta(hours=cap.get("per_hours", 168))
    recent = (
        db.query(PostRecord)
        .filter(PostRecord.destination_id == destination.id)
        .filter(PostRecord.status == "published")
        .filter(PostRecord.created_at >= window_start)
        .count()
    )
    if recent >= cap.get("count", 1):
        reason = f"frequency cap reached: {recent}/{cap.get('count')} posts in last {cap.get('per_hours')}h"
        return RuleCheckResult(ok=False, reason=reason, retry_after=window_start + timedelta(hours=cap.get("per_hours", 168)))
    return RuleCheckResult(ok=True)


def check_self_promo(destination: Destination, is_promotional: bool) -> RuleCheckResult:
    if is_promotional and not destination.self_promo_allowed:
        return RuleCheckResult(ok=False, reason="destination bans self-promotion; content is marked promotional")
    return RuleCheckResult(ok=True)


def check_link_policy(destination: Destination, body: str, canonical_url: str | None) -> RuleCheckResult:
    policy = destination.link_policy or "allowed"
    link_count = body.count("http://") + body.count("https://") + (1 if canonical_url else 0)
    if policy == "none" and link_count > 0:
        return RuleCheckResult(ok=False, reason="destination's link policy is 'none' but content contains a link")
    if policy == "one_link" and link_count > 1:
        return RuleCheckResult(ok=False, reason=f"destination allows at most one link, content has {link_count}")
    return RuleCheckResult(ok=True)


def check_disclosure(destination: Destination, ai_generated: bool, body: str) -> RuleCheckResult:
    if destination.disclosure_required and ai_generated:
        disclosed = "ai-generated" in body.lower() or "ai generated" in body.lower() or "[ai" in body.lower()
        if not disclosed:
            return RuleCheckResult(ok=False, reason="destination requires AI-content disclosure; none found in body")
    return RuleCheckResult(ok=True)


def run_all_checks(db: Session, destination: Destination, rendition) -> list[RuleCheckResult]:
    checks = [
        ("frequency_cap", check_frequency_cap(db, destination)),
        ("self_promo", check_self_promo(destination, rendition.is_promotional)),
        ("link_policy", check_link_policy(destination, rendition.body, rendition.canonical_url)),
        ("disclosure", check_disclosure(destination, rendition.ai_generated, rendition.body)),
    ]
    for rule, result in checks:
        _log(db, destination.id, rule, "passed" if result.ok else "blocked", result.reason)
    return [r for _, r in checks]


def enforce(db: Session, destination: Destination, rendition) -> None:
    """Raises IncuBrixError if any rule blocks the post; returns None if clear."""
    results = run_all_checks(db, destination, rendition)
    failed = [r for r in results if not r.ok]
    if not failed:
        return
    first = failed[0]
    if "frequency cap" in first.reason:
        raise IncuBrixError("DEST_RULE_FREQUENCY_CAP", first.reason,
                             details={"retry_after": first.retry_after.isoformat() if first.retry_after else None})
    if "self-promotion" in first.reason:
        raise IncuBrixError("DEST_RULE_SELF_PROMO_BANNED", first.reason)
    if "link policy" in first.reason:
        raise IncuBrixError("DEST_RULE_LINK_POLICY", first.reason)
    if "disclosure" in first.reason:
        raise IncuBrixError("DEST_RULE_DISCLOSURE_REQUIRED", first.reason)
    raise IncuBrixError("DEST_SPEC_VIOLATION", first.reason)
