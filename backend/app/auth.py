"""JWT issuing/verifying and email-domain gating.

After STC validates a one-time code we mint a short-lived HS256 JWT. Every
protected route verifies that token (see `deps.require_auth`). No refresh
tokens — when the access token expires the user logs in again.
"""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

from .config import get_settings

ALGORITHM = "HS256"


def email_domain_allowed(email: str) -> bool:
    """True if `email` is on the configured domain (case-insensitive). An empty
    `ALLOWED_EMAIL_DOMAIN` disables the restriction."""
    domain = get_settings().allowed_email_domain.strip().lower()
    if not domain:
        return True
    return email.strip().lower().endswith("@" + domain)


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured on the server.",
        )
    return secret


def create_access_token(email: str, user_id: str | None) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    ttl = get_settings().jwt_ttl_minutes * 60
    now = datetime.now(UTC)
    claims = {
        "sub": user_id or email,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM), ttl


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again.",
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        ) from exc
