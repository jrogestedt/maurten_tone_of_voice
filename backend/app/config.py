from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic ---
    anthropic_api_key: str = ""
    # Tiered by task: review is the nuanced semantic/linguistic judgment, so it
    # runs on the most capable model; rewrite is well served by the cheaper one.
    # Prompt caching (see anthropic_client) absorbs most of the review premium.
    anthropic_review_model: str = "claude-opus-4-8"
    anthropic_rewrite_model: str = "claude-sonnet-4-6"
    review_max_tokens: int = 2000
    rewrite_max_tokens: int = 2000

    # --- Storage ---
    # Local default is SQLite. On Railway, attach a Postgres plugin and it will
    # inject DATABASE_URL automatically.
    database_url: str = "sqlite:///./maurten.db"

    # --- Object storage (AWS S3) ---
    # Originals of every reference document live in S3: uploaded files as-is, and
    # pasted text mirrored as a .md. Extracted/entered text still lives in the DB
    # `content` column (the persona read path). Leave bucket empty to disable S3.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-north-1"  # Stockholm; match your bucket's region
    s3_bucket: str = ""
    max_upload_size_mb: int = 25

    # --- Context assembly ---
    # Hard cap on how many characters of reference documents get folded into the
    # system prompt, to keep token usage predictable. ~200k chars ≈ ~50k tokens,
    # which comfortably fits the current 20-30 doc corpus while staying far under
    # the model's 1M context window. The binding cost here is the prompt cache
    # cold-write, not the context window — revisit (distill the corpus into a
    # compact voice spec) when the corpus pushes well past this. See
    # MODEL_COST_AUDIT.md.
    max_context_chars: int = 200000

    # --- CORS ---
    # Comma-separated list of allowed origins. "*" allows all (fine pre-login).
    allowed_origins: str = "*"

    # --- Simple optional protection (legacy; superseded by STC login below) ---
    # If set, every request must send `Authorization: Bearer <api_key>`.
    # Leave empty to disable. Kept only for backwards compatibility.
    api_key: str = ""

    # --- Auth: SportsTec Connect (STC) OTP login ---
    # STC emails a one-time code; we verify it and mint our own JWT.
    # USER_DB_URL already includes the trailing "/api/" path segment.
    user_db_url: str = ""
    user_db_functions_key: str = ""
    user_db_app_id: str = ""

    # JWT we issue after a successful STC code check. Must be set in production.
    jwt_secret: str = ""
    jwt_ttl_minutes: int = 720  # 12h — re-login after expiry (no refresh tokens)

    # Only addresses on this domain may log in. Set empty to allow any domain.
    allowed_email_domain: str = "maurten.com"

    @property
    def origins_list(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
