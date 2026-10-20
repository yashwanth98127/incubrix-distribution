"""Dev.to connector. tier=native. Dev.to is a hosted platform with no local
instance to run, so in SIMULATION_MODE this talks to the bundled mock server
(mocks/platform_mock); set SIMULATION_MODE=false and DEVTO_API_KEY to talk to
the real forem.dev API at the same paths.
"""
from app.connectors.base import Connector
from app.connectors.http_util import call_platform
from app.core.schemas import (
    ValidateRequest, ValidateResponse, PublishRequest, PublishResponse,
    StatusRequest, StatusResponse, DeleteRequest, DeleteResponse,
    MetricsRequest, MetricsResponse,
)
from app.core.errors import IncuBrixError
from app.core.config import settings


class DevtoConnector(Connector):
    key = "devto"
    manifest_file = "devto.yaml"

    def _base_url(self) -> str:
        if settings.SIMULATION_MODE:
            return settings.DEVTO_MOCK_BASE_URL
        return "https://dev.to/api"

    def _headers(self, connection) -> dict:
        api_key = settings.DEVTO_API_KEY if not settings.SIMULATION_MODE else (connection.secret_ref or "sim-key")
        return {"api-key": api_key, "Content-Type": "application/json"}

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

        base = self._base_url()
        resp = call_platform(
            "POST", f"{base}/articles", manifest,
            headers={**self._headers(req.connection), "Idempotency-Key": req.idempotency_key},
            json={"article": {
                "title": req.rendition.title or req.rendition.body[:80],
                "body_markdown": req.rendition.body,
                "published": True,
                "tags": req.rendition.tags[:4],
                "canonical_url": req.rendition.canonical_url,
            }},
        )
        data = resp.json()
        return PublishResponse(platform_post_id=str(data["id"]), live_url=data.get("url", ""), status="published")

    def get_status(self, req: StatusRequest) -> StatusResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        resp = call_platform("GET", f"{base}/articles/{req.platform_post_id}", manifest,
                              headers=self._headers(req.connection))
        data = resp.json()
        return StatusResponse(status="published" if data.get("published") else "deleted", live_url=data.get("url", ""))

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        # Dev.to's public API has no delete endpoint; IncuBrix unpublishes
        # instead (PUT published=false), which is what certification cleanup uses.
        manifest = self.load_manifest()
        base = self._base_url()
        call_platform("PUT", f"{base}/articles/{req.platform_post_id}", manifest,
                       headers=self._headers(req.connection),
                       json={"article": {"published": False}})
        return DeleteResponse(deleted=True)

    def fetch_metrics(self, req: MetricsRequest) -> MetricsResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        resp = call_platform("GET", f"{base}/articles/{req.platform_post_id}", manifest,
                              headers=self._headers(req.connection))
        data = resp.json()
        return MetricsResponse(
            views=data.get("page_views_count", 0),
            likes=data.get("public_reactions_count", 0),
            comments=data.get("comments_count", 0),
        )
