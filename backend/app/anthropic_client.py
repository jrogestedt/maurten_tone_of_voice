import logging

from anthropic import Anthropic
from anthropic.types import MessageParam, TextBlockParam

from .config import get_settings
from .schemas import ReviewResponse

settings = get_settings()
logger = logging.getLogger("maurten.anthropic")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _cached_system(system_prompt: str) -> list[TextBlockParam]:
    """The persona + reference docs as a single cache-marked system block.

    These are static across calls; only the copy under review changes. Marking
    the system prefix with a 1h ephemeral cache turns the bulk of the input
    tokens into ~0.1x cache reads after the first call in a session. The 1h TTL
    (vs the 5m default) keeps the cache warm across the slow human edit loop
    between reviews. Caching is a prefix match, so this only pays off because the
    system prompt is built deterministically (see voice.build_system_prompt).
    """
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
    ]


def _usage_payload(model: str, usage) -> dict:
    """Normalize the SDK usage object into a plain dict for logging + recording."""
    return {
        "model": model,
        "input_tokens": usage.input_tokens or 0,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "output_tokens": usage.output_tokens or 0,
    }


def _log_usage(label: str, payload: dict) -> None:
    logger.info(
        "%s usage: input=%s cache_write=%s cache_read=%s output=%s",
        label,
        payload["input_tokens"],
        payload["cache_creation_input_tokens"],
        payload["cache_read_input_tokens"],
        payload["output_tokens"],
    )


def _guard_stop_reason(label: str, stop_reason: str | None) -> None:
    """Turn the two non-success stop reasons into clear, actionable errors.

    Without this a refusal yields empty content and a max_tokens truncation
    yields half a JSON object — both would otherwise surface as an opaque parse
    failure / 502.
    """
    if stop_reason == "refusal":
        raise RuntimeError(f"{label} was declined by the model's safety system.")
    if stop_reason == "max_tokens":
        raise RuntimeError(
            f"{label} hit the output token limit and was truncated; "
            "increase max_tokens for this call."
        )


def run_review(system_prompt: str, review_prompt: str) -> tuple[dict, dict]:
    """Run a review. Returns (parsed result, usage payload)."""
    client = _get_client()
    model = settings.anthropic_review_model
    messages: list[MessageParam] = [{"role": "user", "content": review_prompt}]
    message = client.messages.parse(
        model=model,
        max_tokens=settings.review_max_tokens,
        system=_cached_system(system_prompt),
        messages=messages,
        # Structured output: the response is constrained to the ReviewResponse
        # schema (incl. the flag/type enums), so there is no brittle JSON
        # extraction and the shape is guaranteed.
        output_format=ReviewResponse,
    )
    usage = _usage_payload(model, message.usage)
    _log_usage("review", usage)
    _guard_stop_reason("Review", message.stop_reason)

    parsed = message.parsed_output
    if parsed is None:
        raise RuntimeError("Review did not return a parseable result.")
    return parsed.model_dump(), usage


def run_rewrite(system_prompt: str, rewrite_prompt: str) -> tuple[str, dict]:
    """Run a rewrite. Returns (rewritten copy, usage payload)."""
    client = _get_client()
    model = settings.anthropic_rewrite_model
    messages: list[MessageParam] = [{"role": "user", "content": rewrite_prompt}]
    message = client.messages.create(
        model=model,
        max_tokens=settings.rewrite_max_tokens,
        system=_cached_system(system_prompt),
        messages=messages,
    )
    usage = _usage_payload(model, message.usage)
    _log_usage("rewrite", usage)
    _guard_stop_reason("Rewrite", message.stop_reason)

    text = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    ).strip()
    return text, usage
