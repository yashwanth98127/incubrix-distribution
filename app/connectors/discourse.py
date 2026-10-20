"""Discourse connector. tier=native. One connector serves every Discourse
forum -- base_url is an instance_param on the Destination, not new code.

In SIMULATION_MODE, instance_params.base_url points at the bundled mock
Discourse server (mocks/platform_mock), which speaks a slimmed-down version
of the real Discourse Admin/Posts API (topics.json, posts.json, etc.).
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


class DiscourseConnector(Connector):
    key = "discourse"
    manifest_file = "discourse.yaml"

    def _base_url(self, destination) -> str:
        return destination.instance_params.get("base_url") or settings.DISCOURSE_MOCK_BASE_URL

    def _headers(self, connection) -> dict:
        api_key = connection.secret_ref or "sim-key"
        username = connection.id or "incubrix-bot"
        return {"Api-Key": api_key, "Api-Username": username, "Content-Type": "application/json"}

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
        resp = call_platform(
            "POST", f"{base}/posts.json", manifest,
            headers={**self._headers(req.connection), "Idempotency-Key": req.idempotency_key},
            json={
                "title": req.rendition.title or req.rendition.body[:80],
                "raw": req.rendition.body,
                "category": req.destination.instance_params.get("category_id", 1),
            },
        )
        data = resp.json()
        return PublishResponse(
            platform_post_id=str(data["id"]),
            live_url=data.get("url") or f"{base}/t/{data['id']}",
            status="published",
        )

    def get_status(self, req: StatusRequest) -> StatusResponse:
        manifest = self.load_manifest()
        base = settings.DISCOURSE_MOCK_BASE_URL
        resp = call_platform("GET", f"{base}/posts/{req.platform_post_id}.json", manifest,
                              headers=self._headers(req.connection))
        data = resp.json()
        return StatusResponse(status=data.get("status", "published"), live_url=data.get("url", ""))

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        manifest = self.load_manifest()
        base = settings.DISCOURSE_MOCK_BASE_URL
        call_platform("DELETE", f"{base}/posts/{req.platform_post_id}.json", manifest,
                       headers=self._headers(req.connection))
        return DeleteResponse(deleted=True)

    def fetch_metrics(self, req: MetricsRequest) -> MetricsResponse:
        manifest = self.load_manifest()
        base = settings.DISCOURSE_MOCK_BASE_URL
        resp = call_platform("GET", f"{base}/posts/{req.platform_post_id}/metrics.json", manifest,
                              headers=self._headers(req.connection))
        data = resp.json()
        return MetricsResponse(
            views=data.get("views", 0), likes=data.get("like_count", 0),
            comments=data.get("reply_count", 0), shares=0, clicks=data.get("clicks", 0),
        )
