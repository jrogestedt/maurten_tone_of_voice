from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(SQLModel, table=True):
    """A reference exemplar of the Maurten voice that informs the model.

    `active=True` documents are folded into the system prompt as voice examples.
    """

    id: int | None = Field(default=None, primary_key=True)
    title: str
    category: str = "general"  # press | social | editorial | retail | product ...
    content: str  # extracted/entered text — the persona read path
    active: bool = True
    # Provenance + original-artifact pointer. The original lives in S3; `content`
    # is always the text the persona reads.
    source_type: str = "text"  # "text" (pasted) | "upload" (file)
    original_filename: str | None = None
    s3_key: str | None = None
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class VoiceConfig(SQLModel, table=True):
    """The core 'Head of Copy' system instructions. Single editable row (id=1)."""

    id: int | None = Field(default=None, primary_key=True)
    prompt: str
    updated_at: datetime = Field(default_factory=_now)


class UserModelPref(SQLModel, table=True):
    """Per-user model selection, keyed by the STC user id (JWT `sub`).

    Each logged-in user independently chooses which model their reviews and
    rewrites run on. Absent a row, the server defaults (config.Settings) apply.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_key: str = Field(index=True, unique=True)  # JWT `sub` (STC id) or email
    email: str = ""
    review_model: str
    rewrite_model: str
    updated_at: datetime = Field(default_factory=_now)


class UsageRecord(SQLModel, table=True):
    """One Anthropic API call's token usage, for cost/usage reporting.

    `cost_usd` is computed and frozen at write time (see usage.py), so historical
    records stay accurate even if the pricing table is later updated.
    """

    id: int | None = Field(default=None, primary_key=True)
    operation: str  # "review" | "rewrite"
    model: str
    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    created_at: datetime = Field(default_factory=_now)
