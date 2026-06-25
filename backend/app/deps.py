from fastapi import Header, HTTPException, status

from .auth import decode_access_token
from .config import get_settings


async def require_auth(authorization: str | None = Header(default=None)) -> dict:
    """Require a valid STC-issued session JWT on every protected route.

    Returns the decoded claims (`sub`, `email`) so handlers can identify the
    caller if needed. Raises 401 when the bearer token is missing or invalid.

    Backwards-compat: if JWT login is not configured (no JWT_SECRET) but the
    legacy API_KEY is set, fall back to the old static-bearer check.
    """
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[len("Bearer ") :].strip()

    # Legacy static-key mode (only when JWT login is not configured).
    if not settings.jwt_secret and settings.api_key:
        if token != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return {"sub": "legacy-api-key", "email": ""}

    return decode_access_token(token)
