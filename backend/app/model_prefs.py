"""Per-user model selection.

Each logged-in STC user independently picks the model used for their reviews and
rewrites. Choices are keyed by the JWT `sub` (the STC user id) and persisted in
UserModelPref. With no stored row, the server defaults (config.Settings) apply.

The selectable set is a curated subset of the priced models in usage.PRICING, so
cost figures shown in the UI and the cost recorded for a call come from one table.
"""

import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from .config import get_settings
from .models import UserModelPref
from .usage import PRICING

logger = logging.getLogger("maurten.model_prefs")

# Curated, user-selectable models (must each exist in usage.PRICING).
MODEL_OPTIONS = [
    {"id": "claude-opus-4-8", "label": "Opus 4.8", "tier": "Highest quality"},
    {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6", "tier": "Balanced"},
    {"id": "claude-haiku-4-5", "label": "Haiku 4.5", "tier": "Fastest & cheapest"},
]
ALLOWED_MODELS = {o["id"] for o in MODEL_OPTIONS}


def options_payload() -> list[dict]:
    """Selectable models joined with their per-MTok pricing (for the UI)."""
    out = []
    for o in MODEL_OPTIONS:
        rates = PRICING.get(o["id"], {})
        out.append(
            {
                "id": o["id"],
                "label": o["label"],
                "tier": o["tier"],
                "input_per_mtok": rates.get("input"),
                "output_per_mtok": rates.get("output"),
            }
        )
    return out


def _user_key(claims: dict) -> str:
    return str(claims.get("sub") or claims.get("email") or "unknown")


def _row(session: Session, claims: dict) -> UserModelPref | None:
    return session.exec(
        select(UserModelPref).where(UserModelPref.user_key == _user_key(claims))
    ).first()


def resolve_user_models(session: Session, claims: dict) -> tuple[str, str]:
    """The (review_model, rewrite_model) this user's calls should use.

    Falls back to the server defaults when the user has no row, or when a stored
    value is no longer in the allowed set (e.g. the catalog changed).
    """
    s = get_settings()
    default_review = s.anthropic_review_model
    default_rewrite = s.anthropic_rewrite_model
    row = _row(session, claims)
    if not row:
        return default_review, default_rewrite
    review = row.review_model if row.review_model in ALLOWED_MODELS else default_review
    rewrite = row.rewrite_model if row.rewrite_model in ALLOWED_MODELS else default_rewrite
    return review, rewrite


def get_preferences(session: Session, claims: dict) -> dict:
    review, rewrite = resolve_user_models(session, claims)
    return {
        "review_model": review,
        "rewrite_model": rewrite,
        "is_default": _row(session, claims) is None,
        "options": options_payload(),
    }


def set_preferences(
    session: Session, claims: dict, review_model: str, rewrite_model: str
) -> dict:
    if review_model not in ALLOWED_MODELS or rewrite_model not in ALLOWED_MODELS:
        raise ValueError("Unsupported model selection.")
    row = _row(session, claims)
    if not row:
        row = UserModelPref(
            user_key=_user_key(claims),
            email=claims.get("email", "") or "",
            review_model=review_model,
            rewrite_model=rewrite_model,
        )
    else:
        row.review_model = review_model
        row.rewrite_model = rewrite_model
        row.email = claims.get("email", "") or row.email
        row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    return get_preferences(session, claims)
