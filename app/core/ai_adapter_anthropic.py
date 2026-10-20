"""Optional real AI adapter. Only imported when AI_PROVIDER=anthropic and an
ANTHROPIC_API_KEY is set -- the default path (mock) never touches this file,
keeping SIMULATION_MODE and CI free of any paid/external dependency."""
from app.core.ai_adapter import AIAdapter, MockAIAdapter
from app.core.config import settings


class AnthropicAIAdapter(AIAdapter):
    provider = "anthropic"

    def __init__(self):
        self._fallback = MockAIAdapter()
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception:
            self._client = None

    def propose_rules(self, rules_page_text: str) -> dict:
        if not self._client:
            return self._fallback.propose_rules(rules_page_text)
        msg = self._client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            messages=[{"role": "user", "content": (
                "Read this community rules page and return ONLY a JSON object with keys "
                "self_promo_allowed (bool), link_policy ('allowed'|'one_link'|'none'), "
                "disclosure_required (bool), frequency_cap ({count, per_hours}). "
                f"Rules page:\n\n{rules_page_text}"
            )}],
        )
        import json
        try:
            return json.loads(msg.content[0].text)
        except Exception:
            return self._fallback.propose_rules(rules_page_text)

    def score_relevance(self, destination_desc, audience):
        return self._fallback.score_relevance(destination_desc, audience)

    def tailor_text(self, body, title, surface_hint):
        return self._fallback.tailor_text(body, title, surface_hint)
