import json
import re

from anthropic import Anthropic

from .config import get_settings

settings = get_settings()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _text_from_response(message) -> str:
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    ).strip()


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("Model did not return JSON")
    return json.loads(match.group(0))


def run_review(system_prompt: str, review_prompt: str) -> dict:
    client = _get_client()
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.review_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": review_prompt}],
    )
    data = _parse_json(_text_from_response(message))

    # Normalise so it always matches the response schema.
    data.setdefault("notes", [])
    for note in data["notes"]:
        note.setdefault("quote", "")
        note.setdefault("fix", "")
    return data


def run_rewrite(system_prompt: str, rewrite_prompt: str) -> str:
    client = _get_client()
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.rewrite_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": rewrite_prompt}],
    )
    return _text_from_response(message)
