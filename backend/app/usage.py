"""Token-usage accounting: pricing, per-call recording, and aggregation.

Costs are computed from the token counts the Anthropic API returns. Cache writes
are priced at the 1-hour-TTL rate (2x base input) because that's the TTL this app
uses (see anthropic_client._cached_system); cache reads are 0.1x base input. If
the caching TTL ever changes, update CACHE_WRITE_MULTIPLIER to match.
"""

import logging

from sqlmodel import Session, func, select

from .models import UsageRecord

logger = logging.getLogger("maurten.usage")

# USD per 1,000,000 tokens, base (uncached) input/output rates per model.
# Keep in sync with MODEL_COST_AUDIT.md and the Anthropic pricing page.
PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-8": {"input": 5.0, "output": 25.0},
    "claude-opus-4-7": {"input": 5.0, "output": 25.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 1.0, "output": 5.0},
}
CACHE_WRITE_MULTIPLIER = 2.0  # 1-hour TTL ephemeral cache write
CACHE_READ_MULTIPLIER = 0.1


def cost_usd(
    model: str,
    input_tokens: int,
    cache_creation_input_tokens: int,
    cache_read_input_tokens: int,
    output_tokens: int,
) -> float:
    """Dollar cost of a single call from its token breakdown."""
    rates = PRICING.get(model)
    if not rates:
        logger.warning("No pricing entry for model %r; recording cost as 0.0", model)
        return 0.0
    inp, out = rates["input"], rates["output"]
    return (
        input_tokens * inp
        + cache_creation_input_tokens * inp * CACHE_WRITE_MULTIPLIER
        + cache_read_input_tokens * inp * CACHE_READ_MULTIPLIER
        + output_tokens * out
    ) / 1_000_000


def record_usage(session: Session, operation: str, usage: dict) -> None:
    """Persist one call's usage. Best-effort: never raise into the request path.

    `usage` is the dict produced by anthropic_client (model + token counts).
    """
    try:
        rec = UsageRecord(
            operation=operation,
            model=usage["model"],
            input_tokens=usage.get("input_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=cost_usd(
                usage["model"],
                usage.get("input_tokens", 0),
                usage.get("cache_creation_input_tokens", 0),
                usage.get("cache_read_input_tokens", 0),
                usage.get("output_tokens", 0),
            ),
        )
        session.add(rec)
        session.commit()
    except Exception:  # noqa: BLE001
        # Usage accounting must never break a review/rewrite. Roll back and log.
        session.rollback()
        logger.exception("Failed to record usage for %s call", operation)


def _group_totals(session: Session, key_col) -> list[dict]:
    rows = session.exec(
        select(
            key_col,
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cache_creation_input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cache_read_input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
        ).group_by(key_col)
    ).all()
    out = []
    for key, calls, inp, cw, cr, outp, cost in rows:
        out.append(
            {
                "key": key,
                "calls": calls,
                "input_tokens": inp,
                "cache_creation_input_tokens": cw,
                "cache_read_input_tokens": cr,
                "output_tokens": outp,
                "cost_usd": round(cost, 4),
            }
        )
    return out


def summarize(session: Session) -> dict:
    """Aggregate totals plus per-model and per-operation breakdowns."""
    totals = session.exec(
        select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cache_creation_input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cache_read_input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
        )
    ).one()
    calls, inp, cw, cr, outp, cost = totals
    since = session.exec(select(func.min(UsageRecord.created_at))).one()

    return {
        "total_calls": calls,
        "total_input_tokens": inp,
        "total_cache_creation_input_tokens": cw,
        "total_cache_read_input_tokens": cr,
        "total_output_tokens": outp,
        "total_tokens": inp + cw + cr + outp,
        "total_cost_usd": round(cost, 4),
        "since": since,
        "by_model": _group_totals(session, UsageRecord.model),
        "by_operation": _group_totals(session, UsageRecord.operation),
    }
