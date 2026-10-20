"""Every external AI service sits behind this adapter, selected by
AI_PROVIDER config (Tools rule #3: swappable providers). The mock adapter
needs no API key so tests and CI run with none.
"""
from app.core.config import settings


class AIAdapter:
    provider = "base"

    def propose_rules(self, rules_page_text: str) -> dict:
        raise NotImplementedError

    def score_relevance(self, destination_desc: str, audience: list[str]) -> tuple[int, str]:
        raise NotImplementedError

    def tailor_text(self, body: str, title: str | None, surface_hint: str) -> tuple[str, str | None]:
        raise NotImplementedError


class MockAIAdapter(AIAdapter):
    """Deterministic, rule-based 'AI' used by default and in all CI/tests.
    Keeps the whole default path commercially usable with zero external calls."""
    provider = "mock"

    FREQUENCY_WORDS = {
        "no self-promotion": {"self_promo_allowed": False},
        "self-promotion is not allowed": {"self_promo_allowed": False},
        "one link": {"link_policy": "one_link"},
        "no links": {"link_policy": "none"},
        "disclose ai": {"disclosure_required": True},
        "ai-generated content must be disclosed": {"disclosure_required": True},
        "once per week": {"frequency_cap": {"count": 1, "per_hours": 168}},
        "once a day": {"frequency_cap": {"count": 1, "per_hours": 24}},
    }

    def propose_rules(self, rules_page_text: str) -> dict:
        text = rules_page_text.lower()
        proposal = {
            "self_promo_allowed": True, "link_policy": "allowed",
            "disclosure_required": False, "frequency_cap": {"count": 1, "per_hours": 168},
        }
        matched = []
        for phrase, patch in self.FREQUENCY_WORDS.items():
            if phrase in text:
                proposal.update(patch)
                matched.append(phrase)
        proposal["_matched_phrases"] = matched
        proposal["_confidence"] = "high" if matched else "low (no rule phrases matched; defaults used)"
        return proposal

    AUDIENCE_KEYWORDS = {
        "ai": ["ai", "machine learning", "llm", "artificial intelligence", "ml"],
        "video": ["video", "streaming", "ctv", "editing"],
        "marketing": ["marketing", "growth", "seo", "content strategy"],
        "saas": ["saas", "software as a service", "b2b software"],
        "creators": ["creator", "youtuber", "influencer", "content creator"],
        "founders": ["founder", "startup", "entrepreneur", "indie hacker"],
    }

    def score_relevance(self, destination_desc: str, audience: list[str]) -> tuple[int, str]:
        text = destination_desc.lower()
        hits = []
        for tag in audience:
            keywords = self.AUDIENCE_KEYWORDS.get(tag.lower(), [tag.lower()])
            if any(k in text for k in keywords):
                hits.append(tag)
        score = min(5, max(1, 1 + len(hits) * 2 if hits else 1))
        if len(hits) >= 2:
            score = 5
        elif len(hits) == 1:
            score = 3
        else:
            score = 1
        reason = f"matched audience tags {hits}" if hits else "no IncuBrix audience keywords (AI/video/marketing/SaaS/creators/founders) found in description"
        return score, reason

    def tailor_text(self, body: str, title: str | None, surface_hint: str) -> tuple[str, str | None]:
        if surface_hint == "forum":
            new_body = f"Discussion: {body}\n\nWould love this community's take -- what am I missing?"
        elif surface_hint == "article":
            new_body = body
        else:
            new_body = body
        return new_body, title


def get_ai_adapter() -> AIAdapter:
    if settings.AI_PROVIDER == "mock":
        return MockAIAdapter()
    if settings.AI_PROVIDER == "anthropic":
        from app.core.ai_adapter_anthropic import AnthropicAIAdapter
        return AnthropicAIAdapter()
    return MockAIAdapter()
