from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..deps import require_auth
from ..models import VoiceConfig
from ..schemas import VoiceConfigRead, VoiceConfigUpdate
from ..voice import DEFAULT_VOICE_PROMPT

router = APIRouter(
    prefix="/api/voice-config", tags=["voice-config"], dependencies=[Depends(require_auth)]
)


def _get_or_create(session: Session) -> VoiceConfig:
    cfg = session.get(VoiceConfig, 1)
    if not cfg:
        cfg = VoiceConfig(id=1, prompt=DEFAULT_VOICE_PROMPT)
        session.add(cfg)
        session.commit()
        session.refresh(cfg)
    return cfg


@router.get("", response_model=VoiceConfigRead)
def get_config(session: Session = Depends(get_session)) -> VoiceConfig:
    return _get_or_create(session)


@router.put("", response_model=VoiceConfigRead)
def update_config(
    payload: VoiceConfigUpdate, session: Session = Depends(get_session)
) -> VoiceConfig:
    cfg = _get_or_create(session)
    cfg.prompt = payload.prompt
    cfg.updated_at = datetime.now(timezone.utc)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg
