from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    review_max_tokens: int = 2000
    rewrite_max_tokens: int = 2000

    # --- Storage ---
    # Local default is SQLite. On Railway, attach a Postgres plugin and it will
    # inject DATABASE_URL automatically.
    database_url: str = "sqlite:///./maurten.db"

    # --- Context assembly ---
    # Hard cap on how many characters of reference documents get folded into the
    # system prompt, to keep token usage predictable.
    max_context_chars: int = 60000

    # --- CORS ---
    # Comma-separated list of allowed origins. "*" allows all (fine pre-login).
    allowed_origins: str = "*"

    # --- Simple optional protection (placeholder until real login) ---
    # If set, every request must send `Authorization: Bearer <api_key>`.
    # Leave empty to disable.
    api_key: str = ""

    @property
    def origins_list(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
