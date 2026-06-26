from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..database import get_session
from ..deps import require_auth
from ..model_prefs import get_preferences, set_preferences
from ..schemas import ModelPreferencesRead, ModelPreferencesUpdate

router = APIRouter(
    prefix="/api/model-preferences",
    tags=["model-preferences"],
    dependencies=[Depends(require_auth)],
)


@router.get("", response_model=ModelPreferencesRead)
def read_preferences(
    session: Session = Depends(get_session),
    claims: dict = Depends(require_auth),
) -> dict:
    return get_preferences(session, claims)


@router.put("", response_model=ModelPreferencesRead)
def update_preferences(
    payload: ModelPreferencesUpdate,
    session: Session = Depends(get_session),
    claims: dict = Depends(require_auth),
) -> dict:
    try:
        return set_preferences(session, claims, payload.review_model, payload.rewrite_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
