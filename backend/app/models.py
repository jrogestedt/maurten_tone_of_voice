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
