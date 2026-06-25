from datetime import datetime

from pydantic import BaseModel, Field, computed_field


# --- Review / Rewrite ---

class ReviewRequest(BaseModel):
    copy: str = Field(min_length=1)
    format: str = "general"
    intent: str = "product"


class ReviewNote(BaseModel):
    flag: str
    type: str
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


# --- Voice config ---

class VoiceConfigUpdate(BaseModel):
    prompt: str = Field(min_length=1)


class VoiceConfigRead(BaseModel):
    prompt: str
    updated_at: datetime


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
