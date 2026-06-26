from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..anthropic_client import run_review, run_rewrite
from ..database import get_session
from ..deps import require_auth
from ..model_prefs import resolve_user_models
from ..usage import record_usage
from ..schemas import (
    OptionsResponse,
    ReviewRequest,
    ReviewResponse,
    RewriteRequest,
    RewriteResponse,
)
from ..voice import (
    FORMAT_LABELS,
    INTENT_LABELS,
    build_review_prompt,
    build_rewrite_prompt,
    build_system_prompt,
)

router = APIRouter(prefix="/api", tags=["review"], dependencies=[Depends(require_auth)])


@router.get("/options", response_model=OptionsResponse)
def options() -> OptionsResponse:
    return OptionsResponse(formats=FORMAT_LABELS, intents=INTENT_LABELS)


@router.post("/review", response_model=ReviewResponse)
def review(
    req: ReviewRequest,
    session: Session = Depends(get_session),
    claims: dict = Depends(require_auth),
) -> ReviewResponse:
    review_model, _ = resolve_user_models(session, claims)
    system_prompt = build_system_prompt(session)
    prompt = build_review_prompt(req.copy, req.format, req.intent)
    try:
        data, usage = run_review(system_prompt, prompt, model=review_model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Review failed: {exc}") from exc
    record_usage(session, "review", usage)
    return ReviewResponse(**data)


@router.post("/rewrite", response_model=RewriteResponse)
def rewrite(
    req: RewriteRequest,
    session: Session = Depends(get_session),
    claims: dict = Depends(require_auth),
) -> RewriteResponse:
    _, rewrite_model = resolve_user_models(session, claims)
    system_prompt = build_system_prompt(session)
    prompt = build_rewrite_prompt(req.copy, req.format, req.intent, req.issues)
    try:
        text, usage = run_rewrite(system_prompt, prompt, model=rewrite_model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Rewrite failed: {exc}") from exc
    record_usage(session, "rewrite", usage)
    return RewriteResponse(rewrite=text)
