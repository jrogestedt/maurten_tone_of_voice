"""Client for SportsTec Connect (STC) — the external OTP provider.

STC's v2 user API delivers and validates one-time login codes by email. The
base URL (`USER_DB_URL`) already includes the `/api` segment, so paths here
must NOT prepend it. Auth is via the `x-functions-key` header.

Mirrors the OTP surface of the mios core-api `stc_client`, trimmed to just the
two calls this app needs: send a code, validate a code.
"""

import logging
from urllib.parse import quote

import httpx

from .config import get_settings

logger = logging.getLogger("maurten.stc")


class StcError(Exception):
    """An STC call failed. `status` is STC's HTTP status, or None for a
    network/config error (no HTTP response)."""

    def __init__(self, status: int | None, detail: str = ""):
        self.status = status
        self.detail = detail
        super().__init__(f"STC error (status={status}): {detail}")


def _config() -> tuple[str, str, str]:
    s = get_settings()
    base = s.user_db_url.rstrip("/")
    if not base or not s.user_db_functions_key:
        raise StcError(None, "STC not configured (USER_DB_URL / USER_DB_FUNCTIONS_KEY missing).")
    if not s.user_db_app_id:
        raise StcError(None, "STC not configured (USER_DB_APP_ID missing).")
    return base, s.user_db_functions_key, s.user_db_app_id


def _request(method: str, path: str, body: dict) -> dict:
    base, key, _ = _config()
    headers = {
        "x-functions-key": key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    try:
        resp = httpx.request(method, f"{base}{path}", json=body, headers=headers, timeout=10.0)
    except Exception as exc:  # noqa: BLE001 — surface as a uniform StcError
        # No HTTP response — DNS, connect timeout, TLS, etc. The path carries the
        # app_id, which is exactly what to compare across environments.
        logger.warning("STC %s %s -> network/config error: %s", method, path, exc)
        raise StcError(None, str(exc)) from exc

    if not resp.is_success:
        logger.warning("STC %s %s -> %s %s", method, path, resp.status_code, resp.reason_phrase)
        raise StcError(resp.status_code, resp.reason_phrase)

    parsed: dict = {}
    if resp.content:
        try:
            parsed = resp.json()
        except ValueError as exc:
            raise StcError(resp.status_code, "Malformed JSON response") from exc

    # Log STC's verdict on a *successful* call. This is the case that otherwise
    # has zero visibility: STC returns 2xx but no email lands. We log the status
    # and the body's top-level keys only — never the OTP code or any value — so a
    # "delivered/queued/failed"-style field shows up without leaking the secret.
    keys = list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__
    logger.info("STC %s %s -> %s; body keys: %s", method, path, resp.status_code, keys)
    return parsed


def send_otp(email: str) -> dict:
    """Ask STC to email a one-time code to `email`."""
    _, _, app_id = _config()
    encoded = quote(email, safe="@.+-_")
    return _request(
        "POST",
        f"/users/{encoded}/applications/{app_id}/otp",
        {"deliveryMethod": "EMAIL", "distribute": True},
    )


def validate_otp(email: str, code: str) -> dict:
    """Validate the code the user entered. On success STC returns the user
    record (we read `id`/`userId` from it)."""
    _, _, app_id = _config()
    encoded = quote(email, safe="@.+-_")
    return _request(
        "POST",
        f"/users/{encoded}/applications/{app_id}/otp/validate",
        {"code": code},
    )
