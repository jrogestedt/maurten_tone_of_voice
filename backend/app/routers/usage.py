from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..deps import require_auth
from ..schemas import UsageSummary
from ..usage import summarize

router = APIRouter(prefix="/api/usage", tags=["usage"], dependencies=[Depends(require_auth)])


@router.get("", response_model=UsageSummary)
def usage(session: Session = Depends(get_session)) -> dict:
    return summarize(session)
