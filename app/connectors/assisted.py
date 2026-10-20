"""Assisted connector (tier=assisted) for communities where automated posting
is not allowed: Slack/Discord communities without bot permission, invite-only
forums, moderated subreddits, etc. It never posts; it builds a ready-to-post
pack and a person submits it. "Certification" for this tier means the pack
builds correctly and a reviewer checklist confirmation is recorded.
"""
from app.connectors.base import Connector
from app.core.schemas import (
    ValidateRequest, ValidateResponse, PublishRequest, PublishResponse,
    StatusRequest, StatusResponse, DeleteRequest, DeleteResponse,
    AssistPackRequest, AssistPackResponse,
)
from app.core.errors import IncuBrixError
from app.core import storage


class AssistedConnector(Connector):
    key = "assisted"
    manifest_file = "assisted.yaml"

    def validate(self, req: ValidateRequest) -> ValidateResponse:
        manifest = self.load_manifest()
        violations = self.check_spec(req.rendition, req.destination, manifest)
        return ValidateResponse(ok=len(violations) == 0, violations=violations)

    def publish(self, req: PublishRequest) -> PublishResponse:
        raise IncuBrixError("CONNECTOR_DISABLED", "assisted connector never auto-publishes; call build_assist_pack")

    def get_status(self, req: StatusRequest) -> StatusResponse:
        return StatusResponse(status="manual_pending", live_url="")

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        return DeleteResponse(deleted=True)

    def build_assist_pack(self, req: AssistPackRequest) -> AssistPackResponse:
        v = self.validate(ValidateRequest(rendition=req.rendition, destination=req.destination))
        if not v.ok:
            raise IncuBrixError("DEST_SPEC_VIOLATION", "content fails destination spec", details={"violations": v.violations})

        caption_parts = []
        if req.rendition.title:
            caption_parts.append(req.rendition.title)
        caption_parts.append(req.rendition.body)
        if req.rendition.ai_generated and req.destination.disclosure_required:
            caption_parts.append("[AI-generated content, disclosed per community rules]")
        caption = "\n\n".join(caption_parts)

        files = []
        for i, url in enumerate(req.rendition.media_urls):
            key = f"assist-packs/{req.destination.id}/media_{i}_{url.rsplit('/', 1)[-1]}"
            files.append(storage.put_json(key + ".ref.json", {"source_url": url}))

        checklist = [
            f"Confirm destination rules at {req.destination.url} are still current",
            "Paste the caption text as-is (do not alter claims)",
            "Attach the media files listed above" if files else "No media to attach",
            "Include the deep link in the post",
            f"Respect frequency cap: {req.destination.frequency_cap}",
        ]
        if not req.destination.self_promo_allowed:
            checklist.append("Self-promotion is banned here: frame as discussion/contribution, not a plug")
        if req.destination.disclosure_required:
            checklist.append("This community requires AI-content disclosure: keep the disclosure line")

        deep_link = req.rendition.canonical_url or req.destination.url

        pack_key = storage.new_key(f"assist-packs/{req.destination.id}", "json")
        pack_url = storage.put_json(pack_key, {
            "destination": req.destination.id,
            "caption": caption,
            "files": files,
            "deep_link": deep_link,
            "checklist": checklist,
        })
        files.append(pack_url)

        return AssistPackResponse(files=files, caption=caption, deep_link=deep_link, checklist=checklist)
