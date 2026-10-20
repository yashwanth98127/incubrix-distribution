"""Per-destination tailoring: discussion-first framing for forums, canonical
URL for articles, truncation at a word boundary, hashtag/mention style."""
from app.core.models import Destination
from app.core.schemas import Rendition


FORUM_PLATFORMS = {"discourse", "lemmy"}
ARTICLE_PLATFORMS = {"devto", "ghost"}


def truncate_at_word_boundary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip() + "…"


def tailor_for_destination(rendition: Rendition, destination: Destination, spec: dict) -> Rendition:
    body = rendition.body
    title = rendition.title
    canonical_url = rendition.canonical_url

    if destination.platform_key in FORUM_PLATFORMS:
        if not body.rstrip().endswith("?"):
            body = f"{body}\n\nCurious what this community thinks -- has anyone tried something similar?"
    elif destination.platform_key in ARTICLE_PLATFORMS:
        canonical_url = canonical_url or destination.instance_params.get("canonical_url")

    if destination.link_policy == "none":
        import re
        body = re.sub(r"https?://\S+", "", body).strip()
        canonical_url = None
    elif destination.link_policy == "one_link" and canonical_url is None and "http" in body:
        pass  # leave the single existing link as-is

    body_max = spec.get("body_max_chars")
    if body_max:
        body = truncate_at_word_boundary(body, body_max)
    title_max = spec.get("title_max_chars")
    if title_max and title:
        title = truncate_at_word_boundary(title, title_max)

    if destination.disclosure_required and rendition.ai_generated:
        disclosure = "[AI-generated content, disclosed per community rules]"
        if disclosure.lower() not in body.lower():
            body = f"{body}\n\n{disclosure}"

    tags = [t.lstrip("#") for t in rendition.tags][:4] if destination.platform_key == "devto" else rendition.tags

    return rendition.model_copy(update={
        "title": title, "body": body, "canonical_url": canonical_url, "tags": tags,
    })
