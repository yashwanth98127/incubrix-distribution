"""Base Connector class implementing the Appendix A contract.

Every connector is stateless and returns results only -- it never writes to
IncuBrix's own database (that's the Connector Runtime's job, simulated here
by app/routes/connector_routes.py + the catalogue tables for demo purposes).
"""
from abc import ABC, abstractmethod
import os
import yaml

from app.core.schemas import (
    ValidateRequest, ValidateResponse,
    PublishRequest, PublishResponse,
    StatusRequest, StatusResponse,
    DeleteRequest, DeleteResponse,
    MetricsRequest, MetricsResponse,
    RefreshAuthRequest, RefreshAuthResponse,
    AssistPackRequest, AssistPackResponse,
)
from app.core.errors import IncuBrixError

MANIFEST_DIR = os.path.join(os.path.dirname(__file__), "manifests")


class Connector(ABC):
    key: str = "base"
    manifest_file: str = ""

    def load_manifest(self) -> dict:
        path = os.path.join(MANIFEST_DIR, self.manifest_file)
        with open(path) as f:
            return yaml.safe_load(f)

    def check_spec(self, rendition, destination, manifest: dict) -> list[str]:
        """Shared spec-limit validation driven by the manifest, used by every connector."""
        violations = []
        surfaces = {s["key"]: s for s in manifest.get("surfaces", [])}
        surface = surfaces.get(destination.surface) or next(iter(surfaces.values()), {})
        spec = surface.get("spec", {})
        content_types = surface.get("content_types", [])

        if rendition.content_type not in content_types and content_types:
            violations.append(f"content_type '{rendition.content_type}' not supported on surface")

        title_max = spec.get("title_max_chars")
        if title_max and rendition.title and len(rendition.title) > title_max:
            violations.append(f"title exceeds {title_max} chars (got {len(rendition.title)})")

        body_max = spec.get("body_max_chars")
        if body_max and len(rendition.body) > body_max:
            violations.append(f"body exceeds {body_max} chars (got {len(rendition.body)})")

        if not spec.get("links_allowed", True) and ("http://" in rendition.body or "https://" in rendition.body):
            violations.append("links are not allowed on this surface")

        media_types = spec.get("accepted_media", None)
        if media_types is not None and rendition.media_urls:
            for m in rendition.media_urls:
                ext = m.rsplit(".", 1)[-1].lower() if "." in m else ""
                if ext not in media_types:
                    violations.append(f"media type '.{ext}' not accepted on this surface")

        return violations

    @abstractmethod
    def validate(self, req: ValidateRequest) -> ValidateResponse: ...

    @abstractmethod
    def publish(self, req: PublishRequest) -> PublishResponse: ...

    @abstractmethod
    def get_status(self, req: StatusRequest) -> StatusResponse: ...

    @abstractmethod
    def delete(self, req: DeleteRequest) -> DeleteResponse: ...

    def fetch_metrics(self, req: MetricsRequest) -> MetricsResponse:
        raise IncuBrixError("NOT_FOUND", f"{self.key} does not implement fetch_metrics")

    def refresh_auth(self, req: RefreshAuthRequest) -> RefreshAuthResponse:
        raise IncuBrixError("NOT_FOUND", f"{self.key} does not implement refresh_auth")

    def build_assist_pack(self, req: AssistPackRequest) -> AssistPackResponse:
        raise IncuBrixError("NOT_FOUND", f"{self.key} does not implement build_assist_pack")
