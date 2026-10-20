"""Ghost connector. tier=native. Talks to the REAL local Ghost instance from
docker-compose (Must-have #8) via the Ghost Admin API, auth'd with a short-
lived JWT signed from a {key_id}:{secret} Admin API key -- never a raw token
in headers or logs.
"""
import time
import jwt as pyjwt

from app.connectors.base import Connector
from app.connectors.http_util import call_platform
from app.core.schemas import (
    ValidateRequest, ValidateResponse, PublishRequest, PublishResponse,
    StatusRequest, StatusResponse, DeleteRequest, DeleteResponse,
    MetricsRequest, MetricsResponse,
)
from app.core.errors import IncuBrixError
from app.core.config import settings


class GhostConnector(Connector):
    key = "ghost"
    manifest_file = "ghost.yaml"

    def _base_url(self, destination=None) -> str:
        if destination and destination.instance_params.get("base_url"):
            return destination.instance_params["base_url"]
        return settings.GHOST_BASE_URL

    def _admin_token(self) -> str:
        admin_key = settings.GHOST_ADMIN_API_KEY
        if not admin_key:
            return "simulated-admin-token"
        key_id, secret = admin_key.split(":")
        iat = int(time.time())
        payload = {"iat": iat, "exp": iat + 300, "aud": "/admin/"}
        token = pyjwt.encode(payload, bytes.fromhex(secret), algorithm="HS256",
                              headers={"kid": key_id})
        return token

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
        token = self._admin_token()
        html = f"<p>{req.rendition.body}</p>"
        resp = call_platform(
            "POST", f"{base}/ghost/api/admin/posts/?source=html", manifest,
            headers={"Authorization": f"Ghost {token}", "Content-Type": "application/json",
                     "Idempotency-Key": req.idempotency_key},
            json={"posts": [{
                "title": req.rendition.title or req.rendition.body[:80],
                "html": html,
                "status": "published",
                "tags": req.rendition.tags,
            }]},
        )
        post = resp.json()["posts"][0]
        return PublishResponse(platform_post_id=post["id"], live_url=post.get("url", ""), status="published")

    def get_status(self, req: StatusRequest) -> StatusResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        token = self._admin_token()
        resp = call_platform("GET", f"{base}/ghost/api/admin/posts/{req.platform_post_id}/", manifest,
                              headers={"Authorization": f"Ghost {token}"})
        post = resp.json()["posts"][0]
        return StatusResponse(status=post.get("status", "published"), live_url=post.get("url", ""))

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        token = self._admin_token()
        call_platform("DELETE", f"{base}/ghost/api/admin/posts/{req.platform_post_id}/", manifest,
                       headers={"Authorization": f"Ghost {token}"})
        return DeleteResponse(deleted=True)

    def fetch_metrics(self, req: MetricsRequest) -> MetricsResponse:
        # Ghost's open-source Admin API has no built-in analytics endpoint;
        # this connector reports zeros rather than fabricating numbers.
        return MetricsResponse()
