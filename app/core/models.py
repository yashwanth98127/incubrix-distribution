import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON

from app.core.db import Base


def gen_id(prefix: str):
    return lambda: f"{prefix}_{uuid.uuid4().hex[:16]}"


class Destination(Base):
    """One catalogue row = one destination. Adding a new instance of a supported
    connector type is a config row here, never new code (Must-have #3)."""
    __tablename__ = "destinations"

    id = Column(String, primary_key=True, default=gen_id("dest"))
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    normalized_url = Column(String, nullable=False, index=True)
    platform_key = Column(String, nullable=False, index=True)  # e.g. discourse, lemmy
    connector_key = Column(String, nullable=False, index=True)  # which connector serves it
    surface = Column(String, default="default")
    category = Column(String, default="")
    audience_tags = Column(JSON, default=list)
    language = Column(String, default="en")
    geo = Column(String, default="")
    est_audience = Column(Integer, default=0)
    rules_url = Column(String, default="")
    frequency_cap = Column(JSON, default=lambda: {"count": 1, "per_hours": 168})
    self_promo_allowed = Column(Boolean, default=True)
    link_policy = Column(String, default="allowed")  # allowed | one_link | none
    disclosure_required = Column(Boolean, default=False)
    automation_allowed = Column(Boolean, default=True)
    relevance_score = Column(Integer, default=3)
    relevance_reason = Column(Text, default="")
    level = Column(String, default="L0")  # L0..L4
    last_certified_at = Column(DateTime, nullable=True)
    instance_params = Column(JSON, default=dict)  # e.g. {"base_url": "...", "community": "..."}
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Connection(Base):
    __tablename__ = "connections"
    id = Column(String, primary_key=True, default=gen_id("conn"))
    destination_id = Column(String, index=True)
    connector_key = Column(String, index=True)
    auth_type = Column(String, default="api_key")
    secret_ref = Column(String, default="")  # never store raw secret; env var name or vault ref
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PostRecord(Base):
    __tablename__ = "post_records"
    id = Column(String, primary_key=True, default=gen_id("post"))
    destination_id = Column(String, index=True)
    connector_key = Column(String, index=True)
    idempotency_key = Column(String, index=True)
    platform_post_id = Column(String, default="")
    live_url = Column(String, default="")
    status = Column(String, default="")  # published | deleted | failed
    is_test_post = Column(Boolean, default=False)
    is_promotional = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)


class CertificationRun(Base):
    __tablename__ = "certification_runs"
    id = Column(String, primary_key=True, default=gen_id("cert"))
    destination_id = Column(String, index=True)
    connector_key = Column(String, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    ok = Column(Boolean, default=False)
    steps = Column(JSON, default=list)  # list of {step, ok, detail, timestamp}
    evidence_path = Column(String, default="")
    level_reached = Column(String, default="L0")
    error = Column(String, default="")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key = Column(String, primary_key=True)
    route = Column(String, nullable=False)
    request_hash = Column(String, default="")
    job_id = Column(String, default="")
    response_body = Column(JSON, default=dict)
    status_code = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=gen_id("job"))
    kind = Column(String, nullable=False)
    status = Column(String, default="queued")  # queued|running|succeeded|failed
    progress = Column(Integer, default=0)
    payload = Column(JSON, default=dict)
    result = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
    callback_url = Column(String, default="")
    correlation_id = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class RuleViolationLog(Base):
    __tablename__ = "rule_violation_log"
    id = Column(String, primary_key=True, default=gen_id("rv"))
    destination_id = Column(String, index=True)
    rule = Column(String, nullable=False)
    outcome = Column(String, nullable=False)  # blocked | rescheduled | passed
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
