"""Generic signed-webhook connector (tier=bridge) for partner sites that don't
have a platform API we can standardise on: IncuBrix POSTs a JSON payload to
the partner's URL, HMAC-SHA256 signed with a shared secret, and the partner's
own system decides what to do with it. One connector, many partners -- each
partner is a catalogue row with its own instance_params.base_url and
instance_params.secret_ref.
"""
import hashlib
import hmac
import json
import time

from app.connectors.base import Connector
from app.connectors.http_util import call_platform
from app.core.schemas import (
    ValidateRequest, ValidateResponse, PublishRequest, PublishResponse,
    StatusRequest, StatusResponse, DeleteRequest, DeleteResponse,
)
from app.core.errors import IncuBrixError
from app.core.config import settings


def sign(secret: str, body: bytes, timestamp: str) -> str:
    msg = f"{timestamp}.{body.decode()}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class WebhookConnector(Connector):
    key = "webhook"
    manifest_file = "webhook.yaml"

    def _base_url(self, destination) -> str:
        return destination.instance_params.get("base_url") or settings.WEBHOOK_RECEIVER_BASE_URL

    def validate(self, req: ValidateRequest) -> ValidateResponse:
        manifest = self.load_manifest()
        violations = self.check_spec(req.rendition, req.destination, manifest)
        if not req.destination.automation_allowed:
            violations.append("destination requires manual/assisted posting, not an automated connector")
        return ValidateResponse(ok=len(violations) == 0, violations=violations)

    def publish(self, req: PublishRequest) -> PublishResponse:
        manifest = self.load_manifest()
        v = self.validate(ValidateRequest(rendition=req.rendition, destination=req.destination, connection=req.connection))
        if not v.ok:
            raise IncuBrixError("DEST_SPEC_VIOLATION", "content fails destination spec", details={"violations": v.violations})

        base = self._base_url(req.destination)
        secret = req.destination.instance_params.get("secret_ref") or settings.WEBHOOK_SHARED_SECRET
        payload = {
            "event": "content.publish",
            "idempotency_key": req.idempotency_key,
            "title": req.rendition.title,
            "body": req.rendition.body,
            "media_urls": req.rendition.media_urls,
            "ai_generated": req.rendition.ai_generated,
        }
        body = json.dumps(payload, sort_keys=True).encode()
        timestamp = str(int(time.time()))
        signature = sign(secret, body, timestamp)

        resp = call_platform(
            "POST", f"{base}/incubrix/webhook", manifest,
            headers={
                "Content-Type": "application/json",
                "X-IncuBrix-Signature": signature,
                "X-IncuBrix-Timestamp": timestamp,
                "Idempotency-Key": req.idempotency_key,
            },
            content=body,
        )
        data = resp.json()
        return PublishResponse(
            platform_post_id=data.get("post_id", req.idempotency_key),
            live_url=data.get("live_url", ""),
            status=data.get("status", "accepted"),
        )

    def get_status(self, req: StatusRequest) -> StatusResponse:
        manifest = self.load_manifest()
        base = settings.WEBHOOK_RECEIVER_BASE_URL
        resp = call_platform("GET", f"{base}/incubrix/webhook/{req.platform_post_id}", manifest)
        data = resp.json()
        return StatusResponse(status=data.get("status", "unknown"), live_url=data.get("live_url", ""))

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        manifest = self.load_manifest()
        base = settings.WEBHOOK_RECEIVER_BASE_URL
        call_platform("DELETE", f"{base}/incubrix/webhook/{req.platform_post_id}", manifest)
        return DeleteResponse(deleted=True)
