from pathlib import Path

from sqlmodel import Session, select

from .models import Document, VoiceConfig
from .voice import DEFAULT_VOICE_PROMPT

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "reference"


def seed(session: Session) -> None:
    # 1. Voice config row.
    if not session.get(VoiceConfig, 1):
        session.add(VoiceConfig(id=1, prompt=DEFAULT_VOICE_PROMPT))
        session.commit()

    # 2. Reference documents — only if the table is empty, so the UI stays the
    #    source of truth afterwards. Drop *.md files into data/reference/ named
    #    like "category__Title.md" (category optional).
    existing = session.exec(select(Document)).first()
    if existing or not REFERENCE_DIR.exists():
        return

    for path in sorted(REFERENCE_DIR.glob("*.md")):
        stem = path.stem
        if "__" in stem:
            category, title = stem.split("__", 1)
        else:
            category, title = "general", stem
        session.add(
            Document(
                title=title.replace("_", " ").strip(),
                category=category.strip().lower(),
                content=path.read_text(encoding="utf-8"),
                active=True,
            )
        )
    session.commit()
