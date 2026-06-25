"""STC OTP login routes.

Flow: POST /api/auth/request-code (email) -> STC emails a code ->
POST /api/auth/verify-code (email + code) -> we mint a JWT.
GET /api/auth/me returns the logged-in identity.

These routes are intentionally NOT behind require_auth (you can't be logged in
yet when you log in). Login is restricted to the configured email domain.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import create_access_token, email_domain_allowed
from ..config import get_settings
from ..deps import require_auth
from ..schemas import (
    MeResponse,
    RequestCodeRequest,
    RequestCodeResponse,
    TokenResponse,
    VerifyCodeRequest,
)
from ..stc_client import StcError, send_otp, validate_otp

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _check_domain(email: str) -> None:
    if not email_domain_allowed(email):
        domain = get_settings().allowed_email_domain
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only @{domain} email addresses may sign in.",
        )


def _stc_http_error(exc: StcError) -> HTTPException:
    if exc.status == 404:
        return HTTPException(status_code=404, detail="No account found for that email.")
    if exc.status in (400, 401, 403):
        return HTTPException(status_code=401, detail="Invalid or expired code.")
    if exc.status is None:
        return HTTPException(status_code=503, detail="Login service is unavailable.")
    return HTTPException(status_code=502, detail="Login service error.")


@router.post("/request-code", response_model=RequestCodeResponse)
def request_code(req: RequestCodeRequest) -> RequestCodeResponse:
    email = req.email.strip()
    _check_domain(email)
    try:
        send_otp(email)
    except StcError as exc:
        raise _stc_http_error(exc) from exc
    return RequestCodeResponse(email=email)


@router.post("/verify-code", response_model=TokenResponse)
def verify_code(req: VerifyCodeRequest) -> TokenResponse:
    email = req.email.strip()
    _check_domain(email)
    try:
        result = validate_otp(email, req.code.strip())
    except StcError as exc:
        raise _stc_http_error(exc) from exc

    user_id = result.get("id") or result.get("userId")
    token, expires_in = create_access_token(email, str(user_id) if user_id else None)
    return TokenResponse(access_token=token, expires_in=expires_in, email=email)


@router.get("/me", response_model=MeResponse)
def me(claims: dict = Depends(require_auth)) -> MeResponse:
    return MeResponse(email=claims.get("email", ""))
