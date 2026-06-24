from fastapi import Header, HTTPException, status

from .config import get_settings

settings = get_settings()


async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """No-op unless API_KEY is configured. Swap this for real session/JWT auth
    when login lands — every protected router already depends on it."""
    if not settings.api_key:
        return
    expected = f"Bearer {settings.api_key}"
    if authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing credentials",
        )
