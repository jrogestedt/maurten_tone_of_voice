from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


# --- Review / Rewrite ---

class ReviewRequest(BaseModel):
    copy: str = Field(min_length=1)
    format: str = "general"
    intent: str = "product"


# These two enums mirror the REVIEW_CONTRACT in voice.py. As Literals they are
# emitted as JSON-schema enums under structured outputs, so the model is
# constrained to valid values and the API response is validated against them too.
ReviewFlag = Literal["red", "amber", "green"]
ReviewNoteType = Literal["Red Line", "Voice", "Structure", "Redundant", "Hydrogel", "Strong"]


class ReviewNote(BaseModel):
    flag: ReviewFlag
    type: ReviewNoteType
    quote: str = ""
    issue: str
    fix: str = ""


class ReviewResponse(BaseModel):
    score: int
    verdict: str
    notes: list[ReviewNote]


class RewriteRequest(BaseModel):
    copy: str = Field(min_length=1)
    format: str = "general"
    intent: str = "product"
    # Optional explicit issues. If omitted, the model rewrites against the voice.
    issues: list[str] = []


class RewriteResponse(BaseModel):
    rewrite: str


# --- Documents ---

class DocumentCreate(BaseModel):
    title: str = Field(min_length=1)
    category: str = "general"
    content: str = Field(min_length=1)
    active: bool = True


class DocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    active: bool | None = None


class DocumentRead(BaseModel):
    id: int
    title: str
    category: str
    content: str
    active: bool
    source_type: str = "text"
    original_filename: str | None = None
    # s3_key is intentionally not exposed; use the download endpoint instead.
    s3_key: str | None = Field(default=None, exclude=True)
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def has_file(self) -> bool:
        return bool(self.s3_key)


class DownloadResponse(BaseModel):
    url: str


class ContextStatus(BaseModel):
    """Health of the active reference corpus against the context budget.

    `level` is computed server-side (see voice.context_status); the frontend
    panel renders the human-readable copy per level.
    """

    level: Literal["ok", "review", "act"]
    active_docs: int
    total_docs: int
    used_chars: int
    active_chars: int
    max_context_chars: int
    fill_pct: float
    dropped_count: int
    dropped_titles: list[str]
    review_model: str
    rewrite_model: str


# --- Voice config ---

class VoiceConfigUpdate(BaseModel):
    prompt: str = Field(min_length=1)


class VoiceConfigRead(BaseModel):
    prompt: str
    updated_at: datetime


# --- Usage / cost reporting ---

class UsageGroupStat(BaseModel):
    key: str  # model id, or operation ("review" / "rewrite")
    calls: int
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int
    cost_usd: float


class UsageSummary(BaseModel):
    total_calls: int
    total_input_tokens: int
    total_cache_creation_input_tokens: int
    total_cache_read_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost_usd: float
    since: datetime | None = None
    by_model: list[UsageGroupStat]
    by_operation: list[UsageGroupStat]


# --- Per-user model selection ---

class ModelOption(BaseModel):
    id: str
    label: str
    tier: str
    input_per_mtok: float | None = None
    output_per_mtok: float | None = None


class ModelPreferencesRead(BaseModel):
    review_model: str
    rewrite_model: str
    is_default: bool
    options: list[ModelOption]


class ModelPreferencesUpdate(BaseModel):
    review_model: str
    rewrite_model: str


# --- Options (for frontend dropdowns) ---

class OptionsResponse(BaseModel):
    formats: dict[str, str]
    intents: dict[str, str]


# --- Auth (STC OTP login) ---

class RequestCodeRequest(BaseModel):
    email: str = Field(min_length=3)


class RequestCodeResponse(BaseModel):
    email: str
    sent: bool = True


class VerifyCodeRequest(BaseModel):
    email: str = Field(min_length=3)
    code: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    email: str


class MeResponse(BaseModel):
    email: str
