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
    content: str
    active: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class VoiceConfig(SQLModel, table=True):
    """The core 'Head of Copy' system instructions. Single editable row (id=1)."""

    id: int | None = Field(default=None, primary_key=True)
    prompt: str
    updated_at: datetime = Field(default_factory=_now)
