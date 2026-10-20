"""Lemmy connector. tier=native. Talks to the REAL local Lemmy instance that
docker-compose brings up (Must-have #8) via the public Lemmy API (api/v3).
instance_param=base_url means one connector serves every Lemmy instance /
community -- adding community #41 is one catalogue row with a new
instance_params.community_name, not new code.
"""
import time
from app.connectors.base import Connector
from app.connectors.http_util import call_platform
from app.core.schemas import (
    ValidateRequest, ValidateResponse, PublishRequest, PublishResponse,
    StatusRequest, StatusResponse, DeleteRequest, DeleteResponse,
)
from app.core.errors import IncuBrixError
from app.core.config import settings

_token_cache: dict[str, tuple[str, float]] = {}


class LemmyConnector(Connector):
    key = "lemmy"
    manifest_file = "lemmy.yaml"

    def _base_url(self, destination=None) -> str:
        if destination and destination.instance_params.get("base_url"):
            return destination.instance_params["base_url"]
        return settings.LEMMY_BASE_URL

    def _login(self, base_url: str) -> str:
        cached = _token_cache.get(base_url)
        if cached and cached[1] > time.time():
            return cached[0]
        manifest = self.load_manifest()
        resp = call_platform("POST", f"{base_url}/api/v3/user/login", manifest, json={
            "username_or_email": settings.LEMMY_USERNAME or "incubrix_bot",
            "password": settings.LEMMY_PASSWORD or "incubrix_dev_password",
        })
        token = resp.json()["jwt"]
        _token_cache[base_url] = (token, time.time() + 3000)
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
        token = self._login(base)
        community_id = req.destination.instance_params.get("community_id", 2)
        resp = call_platform(
            "POST", f"{base}/api/v3/post", manifest,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "name": (req.rendition.title or req.rendition.body[:100])[:200],
                "body": req.rendition.body,
                "community_id": community_id,
                "url": req.rendition.canonical_url,
            },
        )
        data = resp.json()["post_view"]["post"]
        return PublishResponse(
            platform_post_id=str(data["id"]),
            live_url=f"{base}/post/{data['id']}",
            status="published",
        )

    def get_status(self, req: StatusRequest) -> StatusResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        token = self._login(base)
        resp = call_platform("GET", f"{base}/api/v3/post?id={req.platform_post_id}", manifest,
                              headers={"Authorization": f"Bearer {token}"})
        data = resp.json()["post_view"]["post"]
        status = "deleted" if data.get("deleted") else "published"
        return StatusResponse(status=status, live_url=f"{base}/post/{data['id']}")

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        manifest = self.load_manifest()
        base = self._base_url()
        token = self._login(base)
        call_platform("POST", f"{base}/api/v3/post/delete", manifest,
                       headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       json={"post_id": int(req.platform_post_id), "deleted": True})
        return DeleteResponse(deleted=True)
