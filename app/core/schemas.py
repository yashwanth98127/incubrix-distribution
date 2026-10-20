"""Pydantic models for the connector contract (Appendix A)."""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class Rendition(BaseModel):
    """The piece of content tailored for one destination surface."""
    title: Optional[str] = None
    body: str
    content_type: Literal["text", "image", "video_link", "article"] = "text"
    media_urls: list[str] = Field(default_factory=list)
    canonical_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    ai_generated: bool = False
    is_promotional: bool = False


class DestinationRef(BaseModel):
    id: str
    name: str
    url: str
    platform_key: str
    surface: str = "default"
    frequency_cap: dict = Field(default_factory=lambda: {"count": 1, "per_hours": 168})
    self_promo_allowed: bool = True
    link_policy: str = "allowed"
    disclosure_required: bool = False
    automation_allowed: bool = True
    instance_params: dict = Field(default_factory=dict)


class Connection(BaseModel):
    id: str = ""
    auth_type: str = "api_key"
    secret_ref: str = ""
    expires_at: Optional[str] = None


class ValidateRequest(BaseModel):
    rendition: Rendition
    destination: DestinationRef
    connection: Connection = Connection()


class ValidateResponse(BaseModel):
    ok: bool
    violations: list[str] = Field(default_factory=list)


class PublishRequest(BaseModel):
    rendition: Rendition
    destination: DestinationRef
    connection: Connection = Connection()
    idempotency_key: str


class PublishResponse(BaseModel):
    platform_post_id: str
    live_url: str
    status: str


class StatusRequest(BaseModel):
    platform_post_id: str
    connection: Connection = Connection()


class StatusResponse(BaseModel):
    status: str
    live_url: str = ""


class DeleteRequest(BaseModel):
    platform_post_id: str
    connection: Connection = Connection()


class DeleteResponse(BaseModel):
    deleted: bool


class MetricsRequest(BaseModel):
    platform_post_id: str
    connection: Connection = Connection()
    since: Optional[str] = None


class MetricsResponse(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    watch_time_s: int = 0
    clicks: int = 0


class RefreshAuthRequest(BaseModel):
    connection: Connection = Connection()


class RefreshAuthResponse(BaseModel):
    expires_at: str


class AssistPackRequest(BaseModel):
    rendition: Rendition
    destination: DestinationRef


class AssistPackResponse(BaseModel):
    files: list[str] = Field(default_factory=list)
    caption: str
    deep_link: str
    checklist: list[str] = Field(default_factory=list)
