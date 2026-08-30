import os

from google import genai

from ..models import SentimentResult

# Used only if a live models.list() call fails (offline, bad key, etc.) so
# the dropdown in the UI is never empty. This list will go stale as Google
# ships new models — that's expected and fine, since list_models() below
# always prefers the live result over this fallback.
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
]
DEFAULT_MODEL = "gemini-2.5-flash"


def list_models(api_key: str) -> list[str]:
    """
    Live list of Gemini models that support generateContent, newest-ish
    first. This replaces the old hardcoded model string entirely — v1 was
    broken because gemini-2.0-flash was silently retired server-side and
    nothing in the code could adapt to that.
    """
    if not api_key:
        return FALLBACK_MODELS
    try:
        client = genai.Client(api_key=api_key)
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if "generateContent" not in actions:
                continue
            short_name = m.name.split("/")[-1] if m.name else None
            if not short_name or "embedding" in short_name or "imagen" in short_name or "veo" in short_name:
                continue
            names.append(short_name)
        return sorted(set(names), reverse=True) or FALLBACK_MODELS
    except Exception:
        return FALLBACK_MODELS


class AnalysisEngine:
    def __init__(self, model_id: str = DEFAULT_MODEL):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found. Set it in your .env file.")
        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id

    def analyze_content(self, text: str) -> dict:
        """
        Returns a dict with sentiment/score/reasoning/language, or raises
        on failure (the orchestrator decides how to log/handle it — the
        old code swallowed every error here and returned None, which made
        failures invisible).
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=f"Analyze the sentiment of this social media post:\n\n{text}",
                config={
                    "response_mime_type": "application/json",
                    "response_schema": SentimentResult,
                },
            )
        except Exception as e:
            if "404" in str(e) or "NOT_FOUND" in str(e):
                raise RuntimeError(
                    f"Model '{self.model_id}' isn't available anymore. "
                    "Open Settings and pick a different one from the dropdown — "
                    "it's fetched live from Google, so it always reflects what's "
                    "currently offered."
                ) from e
            raise
        return response.parsed.model_dump()
