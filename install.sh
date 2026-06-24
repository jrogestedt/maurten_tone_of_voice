#!/usr/bin/env bash
# Maurten Tone of Voice — installer.
# Run from the root of your repo. Writes the full backend/ + frontend/ tree.
set -euo pipefail
echo "Writing Maurten ToV project files into $(pwd)"

mkdir -p "backend"
mkdir -p "backend/app"
mkdir -p "backend/app/routers"
mkdir -p "backend/data/reference"
mkdir -p "frontend"
mkdir -p "frontend/src"
mkdir -p "frontend/src/components"

cat > ".gitignore" << '__MAURTEN_EOF__'
# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.db
.env

# Node
node_modules/
dist/
.vite/

# OS
.DS_Store
__MAURTEN_EOF__

cat > "README.md" << '__MAURTEN_EOF__'
# Maurten Tone of Voice

The brand-voice reviewer, rebuilt as a deployable app: a Python API that calls
Claude with the Maurten "Head of Copy" persona, a React frontend, and storage
for the reference corpus that informs the model.

The original tool worked by copy-pasting prompts in and out of a chat. This
version calls the Anthropic API directly from the backend, so the frontend (and
any other service) just hits clean HTTP endpoints.

```
maurten-tov/
├── backend/          FastAPI + SQLModel + Anthropic SDK
│   ├── app/
│   │   ├── main.py            app, CORS, routers, startup seed
│   │   ├── config.py          env settings
│   │   ├── database.py        engine/session (SQLite local, Postgres prod)
│   │   ├── models.py          Document, VoiceConfig tables
│   │   ├── schemas.py         request/response models
│   │   ├── voice.py           persona, format/intent maps, prompt builders
│   │   ├── anthropic_client.py  review/rewrite calls + JSON parsing
│   │   ├── deps.py            optional API-key auth (placeholder for login)
│   │   ├── seed.py            seeds voice config + reference docs
│   │   └── routers/           review, documents, voice_config
│   └── data/reference/        seed corpus (*.md, "category__Title.md")
└── frontend/         Vite + React
    └── src/
        ├── api.js
        └── components/  Reviewer, Documents, VoiceConfig
```

## API

| Method | Path                  | Purpose                                   |
|--------|-----------------------|-------------------------------------------|
| GET    | `/health`             | Liveness + active model                   |
| GET    | `/api/options`        | Format + intent label maps                |
| POST   | `/api/review`         | `{copy, format, intent}` → review JSON     |
| POST   | `/api/rewrite`        | `{copy, format, intent, issues[]}` → text |
| GET/POST | `/api/documents`    | List / create reference docs              |
| GET/PUT/DELETE | `/api/documents/{id}` | Read / update / delete            |
| GET/PUT | `/api/voice-config`  | Read / edit the core persona prompt       |

Interactive docs at `/docs` once running.

How context is assembled: every review/rewrite sends the **voice config**
prompt plus all **active** reference documents as the system prompt, capped at
`MAX_CONTEXT_CHARS`. Toggle documents on/off from the Reference Docs tab.

## Local development

Backend:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

Frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api to :8000
```

## Deploy to Railway

Two services from this one repo, plus a Postgres plugin.

**1. Backend service**
- New service → deploy from repo → set **Root Directory** to `backend`.
- Add the **Postgres** plugin to the project. It injects `DATABASE_URL` into the
  backend automatically (the app normalises the URL scheme).
- Variables: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, and once the frontend
  exists, `ALLOWED_ORIGINS=https://<frontend-domain>`.
- Start command is read from `backend/railway.toml`.

**2. Frontend service**
- New service → same repo → set **Root Directory** to `frontend`.
- Variable: `VITE_API_BASE_URL=https://<backend-domain>`.
- Nixpacks runs `npm run build`; `frontend/railway.toml` serves `dist`.

**3. Wire CORS**
- Set the backend's `ALLOWED_ORIGINS` to the frontend's public URL and redeploy.

## Adding login (later)

`app/deps.py` has a `require_auth` dependency that every protected router already
uses. Today it only enforces a bearer token if you set `API_KEY` — a quick way
to lock things down before real auth. Replace its body with session/JWT
verification when login lands; nothing else needs to change.

## Managing the corpus

Drop `*.md` files into `backend/data/reference/` named `category__Title.md` and
they seed on first boot (empty DB only). After that, the **Reference Docs** tab
is the source of truth — add, edit, activate/deactivate, or delete.
__MAURTEN_EOF__

cat > "backend/.env.example" << '__MAURTEN_EOF__'
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Model — set to whatever your account has access to
ANTHROPIC_MODEL=claude-sonnet-4-6

# Storage. Local dev defaults to SQLite. On Railway, add a Postgres plugin and
# it injects DATABASE_URL automatically — leave this unset there.
# DATABASE_URL=postgresql://user:pass@host:5432/db

# CORS — set to your frontend URL in production, e.g. https://yourapp.up.railway.app
ALLOWED_ORIGINS=*

# Optional simple protection until real login (Bearer token on every request)
# API_KEY=some-long-random-string

# Tuning
REVIEW_MAX_TOKENS=2000
REWRITE_MAX_TOKENS=2000
MAX_CONTEXT_CHARS=60000
__MAURTEN_EOF__

cat > "backend/Procfile" << '__MAURTEN_EOF__'
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
__MAURTEN_EOF__

touch "backend/app/__init__.py"

cat > "backend/app/anthropic_client.py" << '__MAURTEN_EOF__'
import json
import re

from anthropic import Anthropic

from .config import get_settings

settings = get_settings()

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _text_from_response(message) -> str:
    return "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    ).strip()


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        raise ValueError("Model did not return JSON")
    return json.loads(match.group(0))


def run_review(system_prompt: str, review_prompt: str) -> dict:
    client = _get_client()
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.review_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": review_prompt}],
    )
    data = _parse_json(_text_from_response(message))

    # Normalise so it always matches the response schema.
    data.setdefault("notes", [])
    for note in data["notes"]:
        note.setdefault("quote", "")
        note.setdefault("fix", "")
    return data


def run_rewrite(system_prompt: str, rewrite_prompt: str) -> str:
    client = _get_client()
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=settings.rewrite_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": rewrite_prompt}],
    )
    return _text_from_response(message)
__MAURTEN_EOF__

cat > "backend/app/config.py" << '__MAURTEN_EOF__'
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    review_max_tokens: int = 2000
    rewrite_max_tokens: int = 2000

    # --- Storage ---
    # Local default is SQLite. On Railway, attach a Postgres plugin and it will
    # inject DATABASE_URL automatically.
    database_url: str = "sqlite:///./maurten.db"

    # --- Context assembly ---
    # Hard cap on how many characters of reference documents get folded into the
    # system prompt, to keep token usage predictable.
    max_context_chars: int = 60000

    # --- CORS ---
    # Comma-separated list of allowed origins. "*" allows all (fine pre-login).
    allowed_origins: str = "*"

    # --- Simple optional protection (placeholder until real login) ---
    # If set, every request must send `Authorization: Bearer <api_key>`.
    # Leave empty to disable.
    api_key: str = ""

    @property
    def origins_list(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
__MAURTEN_EOF__

cat > "backend/app/database.py" << '__MAURTEN_EOF__'
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


def _normalize_db_url(url: str) -> str:
    """Railway/Heroku hand out `postgres://...`. SQLAlchemy + psycopg v3 needs
    the `postgresql+psycopg://` scheme."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


settings = get_settings()
DB_URL = _normalize_db_url(settings.database_url)

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    # Import models so SQLModel sees the tables before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
__MAURTEN_EOF__

cat > "backend/app/deps.py" << '__MAURTEN_EOF__'
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
__MAURTEN_EOF__

cat > "backend/app/main.py" << '__MAURTEN_EOF__'
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from .config import get_settings
from .database import engine, init_db
from .routers import documents, review, voice_config
from .seed import seed

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        seed(session)
    yield


app = FastAPI(title="Maurten Tone of Voice API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review.router)
app.include_router(documents.router)
app.include_router(voice_config.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "model": settings.anthropic_model}
__MAURTEN_EOF__

cat > "backend/app/models.py" << '__MAURTEN_EOF__'
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Document(SQLModel, table=True):
    """A reference exemplar of the Maurten voice that informs the model.

    `active=True` documents are folded into the system prompt as voice examples.
    """

    id: int | None = Field(default=None, primary_key=True)
    title: str
    category: str = "general"  # press | social | editorial | retail | product ...
    content: str
    active: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class VoiceConfig(SQLModel, table=True):
    """The core 'Head of Copy' system instructions. Single editable row (id=1)."""

    id: int | None = Field(default=None, primary_key=True)
    prompt: str
    updated_at: datetime = Field(default_factory=_now)
__MAURTEN_EOF__

touch "backend/app/routers/__init__.py"

cat > "backend/app/routers/documents.py" << '__MAURTEN_EOF__'
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import require_auth
from ..models import Document
from ..schemas import DocumentCreate, DocumentRead, DocumentUpdate

router = APIRouter(
    prefix="/api/documents", tags=["documents"], dependencies=[Depends(require_auth)]
)


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_session)) -> list[Document]:
    return session.exec(select(Document).order_by(Document.updated_at.desc())).all()


@router.post("", response_model=DocumentRead, status_code=201)
def create_document(
    payload: DocumentCreate, session: Session = Depends(get_session)
) -> Document:
    doc = Document(**payload.model_dump())
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.get("/{doc_id}", response_model=DocumentRead)
def get_document(doc_id: int, session: Session = Depends(get_session)) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int, payload: DocumentUpdate, session: Session = Depends(get_session)
) -> Document:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    doc.updated_at = datetime.now(timezone.utc)
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: int, session: Session = Depends(get_session)) -> None:
    doc = session.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    session.delete(doc)
    session.commit()
__MAURTEN_EOF__

cat > "backend/app/routers/review.py" << '__MAURTEN_EOF__'
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..anthropic_client import run_review, run_rewrite
from ..database import get_session
from ..deps import require_auth
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
def review(req: ReviewRequest, session: Session = Depends(get_session)) -> ReviewResponse:
    system_prompt = build_system_prompt(session)
    prompt = build_review_prompt(req.copy, req.format, req.intent)
    try:
        data = run_review(system_prompt, prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Review failed: {exc}") from exc
    return ReviewResponse(**data)


@router.post("/rewrite", response_model=RewriteResponse)
def rewrite(req: RewriteRequest, session: Session = Depends(get_session)) -> RewriteResponse:
    system_prompt = build_system_prompt(session)
    prompt = build_rewrite_prompt(req.copy, req.format, req.intent, req.issues)
    try:
        text = run_rewrite(system_prompt, prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Rewrite failed: {exc}") from exc
    return RewriteResponse(rewrite=text)
__MAURTEN_EOF__

cat > "backend/app/routers/voice_config.py" << '__MAURTEN_EOF__'
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
__MAURTEN_EOF__

cat > "backend/app/schemas.py" << '__MAURTEN_EOF__'
from datetime import datetime

from pydantic import BaseModel, Field


# --- Review / Rewrite ---

class ReviewRequest(BaseModel):
    copy: str = Field(min_length=1)
    format: str = "general"
    intent: str = "product"


class ReviewNote(BaseModel):
    flag: str
    type: str
    quote: str = ""
    issue: str
    fix: str = ""


class ReviewResponse(BaseModel):
    score: int
    verdict: str
    notes: list[ReviewNote]


class RewriteRequest(BaseModel):
    copy: str = Field(min_length=1)
    format: str = "general"
    intent: str = "product"
    # Optional explicit issues. If omitted, the model rewrites against the voice.
    issues: list[str] = []


class RewriteResponse(BaseModel):
    rewrite: str


# --- Documents ---

class DocumentCreate(BaseModel):
    title: str = Field(min_length=1)
    category: str = "general"
    content: str = Field(min_length=1)
    active: bool = True


class DocumentUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    content: str | None = None
    active: bool | None = None


class DocumentRead(BaseModel):
    id: int
    title: str
    category: str
    content: str
    active: bool
    created_at: datetime
    updated_at: datetime


# --- Voice config ---

class VoiceConfigUpdate(BaseModel):
    prompt: str = Field(min_length=1)


class VoiceConfigRead(BaseModel):
    prompt: str
    updated_at: datetime


# --- Options (for frontend dropdowns) ---

class OptionsResponse(BaseModel):
    formats: dict[str, str]
    intents: dict[str, str]
__MAURTEN_EOF__

cat > "backend/app/seed.py" << '__MAURTEN_EOF__'
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
__MAURTEN_EOF__

cat > "backend/app/voice.py" << '__MAURTEN_EOF__'
from sqlmodel import Session, select

from .config import get_settings
from .models import Document, VoiceConfig

settings = get_settings()


# The default "Head of Copy" system prompt. Stored in the DB on first run and
# editable from the frontend, so this is only the seed value.
DEFAULT_VOICE_PROMPT = """You are the Maurten Head of Copy. Review, rewrite, and advise on brand copy with authority and precision.

Voice:

Economy of language. Fragmented sentence rhythm. Trust the reader to complete the thought. Subtle confidence — the product works; the copy doesn't need to prove it. Default to less. If a line can be cut, cut it. Speak to athletes as peers. Acknowledge the rituals, routines, and compulsions of endurance sport. Acknowledge the hard edges. Never smooth them.

Beckett rhythm throughout. Abstraction is permitted in campaign and athlete content — not in product and education copy.

Hydrogel Technology is central to all product communication. Ground it in what it actually does.

Red lines — never:

No clichés. No influencer theatrics. No content for the sake of filling a feed. No glorification. No exaggerated claims or soft science. No motivational preaching. No polishing of the hard edges of endurance life. No em dashes. No "this isn't X, it's Y" clause formatting. No emojis. No profanities.
"""


# Mirror of the maps in the original HTML tool. Kept server-side so every
# consumer of the API gets identical behaviour.
FORMAT_LABELS: dict[str, str] = {
    "general": "copy",
    "pdp": "PDP copy",
    "newsletter": "newsletter copy",
    "social": "social copy",
    "ad": "ad copy",
    "press": "press release",
    "retail": "retail guide",
    "editorial": "editorial copy",
}

INTENT_LABELS: dict[str, str] = {
    "product": "Product-led. Product mentions and Hydrogel Technology references are expected and appropriate.",
    "reactive": "Reactive moment caption. Responds to a specific athlete performance or event. No commercial objective. Do NOT flag absence of product mentions. Evaluate purely on voice, rhythm, and whether it captures the moment honestly.",
    "athlete": "Athlete story. Focus is the athlete and their experience. Product mention optional, not required.",
    "education": "Educational content. Clarity and accuracy matter most. Product grounding appropriate where relevant.",
    "brand": "Brand or awareness. No product push expected. Voice and tone are the primary criteria.",
}

REVIEW_CONTRACT = (
    "Return JSON only, no preamble, no markdown fences:\n"
    '{"score":<1-10>,"verdict":"<one blunt sentence>","notes":'
    '[{"flag":"red|amber|green","type":"<Red Line|Voice|Structure|Redundant|Hydrogel|Strong>",'
    '"quote":"<exact phrase max 12 words or empty string>","issue":"<direct editorial note>",'
    '"fix":"<suggestion or empty string>"}]}\n'
    "3-8 notes. Direct. No softening."
)


def fmt_label(key: str) -> str:
    return FORMAT_LABELS.get(key, FORMAT_LABELS["general"])


def intent_label(key: str) -> str:
    return INTENT_LABELS.get(key, INTENT_LABELS["product"])


def get_voice_prompt(session: Session) -> str:
    cfg = session.get(VoiceConfig, 1)
    return cfg.prompt if cfg else DEFAULT_VOICE_PROMPT


def build_system_prompt(session: Session) -> str:
    """Persona + active reference documents, capped at max_context_chars."""
    parts = [get_voice_prompt(session)]

    docs = session.exec(
        select(Document).where(Document.active == True)  # noqa: E712
    ).all()

    if docs:
        budget = settings.max_context_chars
        examples: list[str] = []
        for doc in docs:
            block = f"### {doc.title} ({doc.category})\n{doc.content}"
            if budget - len(block) < 0:
                break
            examples.append(block)
            budget -= len(block)
        if examples:
            parts.append(
                "Below are reference examples of the Maurten voice. Use them to "
                "calibrate tone, rhythm, and register. Do not quote them back.\n\n"
                + "\n\n".join(examples)
            )

    return "\n\n".join(parts)


def build_review_prompt(copy: str, fmt_key: str, intent_key: str) -> str:
    return (
        "MAURTEN VOICE REVIEW\n"
        f"Format: {fmt_label(fmt_key)}\n"
        f"Intent: {intent_label(intent_key)}\n\n"
        "Copy to review:\n\n"
        f"{copy}\n\n"
        "---\n"
        f"{REVIEW_CONTRACT}"
    )


def build_rewrite_prompt(copy: str, fmt_key: str, intent_key: str, issues: list[str]) -> str:
    issues_block = "\n".join(f"- {i}" for i in issues) if issues else "- Apply the Maurten voice throughout."
    return (
        "MAURTEN VOICE REWRITE\n"
        f"Format: {fmt_label(fmt_key)}\n"
        f"Intent: {intent_label(intent_key)}\n\n"
        "Original copy:\n\n"
        f"{copy}\n\n"
        "Issues to fix:\n"
        f"{issues_block}\n\n"
        "---\n"
        "Rewrite the copy so it scores at least 8/10 against the Maurten Voice. "
        "Apply the Maurten voice: economy of language, fragmented sentence rhythm, "
        "subtle confidence, no embellishment, athlete-peer register. Fix all red line "
        "violations and amber notes. Return the rewritten copy only — no explanation, "
        "no preamble, no score."
    )
__MAURTEN_EOF__

cat > "backend/data/reference/editorial__Kilian_Jornet_100_mile.md" << '__MAURTEN_EOF__'
"Why am I here? Come on, just stop. Just stop!"

The path of least resistance can be a tempting one — even for an ultra runner of Kilian Jornet's calibre. It's the trail-side siren serenading the loneliness of arguably the greatest long-distance runner of them all.

Humans are intrinsically wired to look for the easy way out. We also possess an inherent need for motion. These two instincts lock horns when a foot race stretches to 15 hours, 20 hours, and beyond.

"No emotions, that's the goal. You spend energy on emotions. When you make decisions, emotions are the main things that make you choose one thing or another. Which is super cool in life, but when you're racing, it's not the best approach."

It's a lot of counting. Counting up. Counting down. Counting steps. Counting calories.

"It's like you're in a bubble — you're somewhere else. Your body is moving towards one direction, and your mind is on another path."
__MAURTEN_EOF__

cat > "backend/data/reference/press__Additions_launch.md" << '__MAURTEN_EOF__'
Maurten launches Additions — optional taste layers to Drink Mix.

Maurten transformed the way athletes fuel — with Hydrogel Technology the catalyst to a carbohydrate revolution in endurance sports. Today, the Swedish brand introduces an optional taste layer to Drink Mix 160 and 320, called Additions.

"For some athletes, flavor fatigue is real, even when the products are clean and neutral," says Olof Skold, Maurten CEO. "It can become a limitation to consistent fueling — especially over really long efforts or training blocks. So we worked on a bypass. Additions are the result."

Maurten Additions are a palate reset. A way to overcome flavor fatigue during training and racing — so athletes can fuel consistently with the Hydrogel Technology that helps them tolerate more carbohydrates.

Available in Cola, Apple, Menthol, and Orange.
__MAURTEN_EOF__

cat > "backend/data/reference/retail__Gel_Mix_480_copy.md" << '__MAURTEN_EOF__'
A new consistency.

Long efforts demand more. Not just in distance or duration — in how they're fueled. Gel Mix 480 brings Hydrogel Technology into every long session that counts. Consistently — race day or training. A different texture. A new habit. Same standard.

Thicker than Drink Mix and looser than Gel, it contains 120 grams of carbohydrates per serving when dissolved in 200 ml of water. Gel Mix 480 is pH-sensitive — like Drink Mix, it becomes a true gel in the acidity of the stomach. This change encapsulates the carbohydrates and carries them through the stomach to be absorbed and used as fuel.

One sachet. 120 grams of carbohydrates. Enough to fuel a long effort — or split across two.
__MAURTEN_EOF__

cat > "backend/data/reference/social__Demi_Vollering.md" << '__MAURTEN_EOF__'
Demi Vollering manifested her brutal attack on the Oude Kwaremont during fitful nights before Sunday's Tour of Flanders.

It was then she visualized her brutal attack on the Oude Kwaremont. Playing and replaying the moment. Building belief. Putting it out there.

When the famed cobbled climb arrived, she reacted. Second nature. One by one, her breakaway contemporaries dropped from her wheel.

She'd seen this film before and she loved the ending.

Some call it manifestation. Others call it preparation. It doesn't matter.

The move. The timing. The outcome. Played. Replayed.

So when it came, she didn't think. She went.

Demi Vollering. 2026 Tour of Flanders champion.
__MAURTEN_EOF__

cat > "backend/data/reference/social__Eliud_Kipchoge.md" << '__MAURTEN_EOF__'
Greatness can be measured in many ways. What sets Eliud apart — what elevates him to a plane without peers — is his ability to make the world stand still in expectation and awe every time he takes on the ancient distance. He possesses a gift to unite, inspire hope, and make people dust off their running shoes and dare to dream a little.

A master continually refines their craft, and today, in Berlin, Eliud Kipchoge showed once again why, when he runs, the planet watches.

02:xx:xx. Congratulations on your new world record, Champ.
__MAURTEN_EOF__

cat > "backend/railway.toml" << '__MAURTEN_EOF__'
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "on_failure"
__MAURTEN_EOF__

cat > "backend/requirements.txt" << '__MAURTEN_EOF__'
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlmodel==0.0.22
psycopg[binary]==3.2.3
anthropic==0.42.0
pydantic==2.10.4
pydantic-settings==2.7.0
__MAURTEN_EOF__

cat > "frontend/.env.example" << '__MAURTEN_EOF__'
# Base URL of the backend API. Leave empty in local dev (Vite proxies /api).
# In production set to your backend Railway URL, e.g. https://maurten-api.up.railway.app
VITE_API_BASE_URL=
__MAURTEN_EOF__

cat > "frontend/index.html" << '__MAURTEN_EOF__'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>M. Brand Voice Reviewer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
__MAURTEN_EOF__

cat > "frontend/package.json" << '__MAURTEN_EOF__'
{
  "name": "maurten-tov-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "start": "serve -s dist -l ${PORT:-3000}"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "serve": "^14.2.4"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^6.0.5"
  }
}
__MAURTEN_EOF__

cat > "frontend/railway.toml" << '__MAURTEN_EOF__'
[build]
builder = "nixpacks"

[deploy]
startCommand = "serve -s dist -l $PORT"
restartPolicyType = "on_failure"
__MAURTEN_EOF__

cat > "frontend/src/App.jsx" << '__MAURTEN_EOF__'
import { useState } from "react";
import Reviewer from "./components/Reviewer.jsx";
import Documents from "./components/Documents.jsx";
import VoiceConfig from "./components/VoiceConfig.jsx";

export default function App() {
  const [tab, setTab] = useState("reviewer");

  return (
    <>
      <div className="header">
        <span className="header-logo">M.</span>
        <span className="header-divider">/</span>
        <span className="header-title">Brand Voice Reviewer</span>
        <span className="header-tag">Head of Copy</span>
      </div>

      <div className="nav">
        <button className={tab === "reviewer" ? "active" : ""} onClick={() => setTab("reviewer")}>
          Reviewer
        </button>
        <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
          Reference Docs
        </button>
        <button className={tab === "voice" ? "active" : ""} onClick={() => setTab("voice")}>
          Voice Config
        </button>
      </div>

      {tab === "reviewer" && <Reviewer />}
      {tab === "documents" && <Documents />}
      {tab === "voice" && <VoiceConfig />}
    </>
  );
}
__MAURTEN_EOF__

cat > "frontend/src/api.js" << '__MAURTEN_EOF__'
const BASE = import.meta.env.VITE_API_BASE_URL || "";

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  options: () => req("/api/options"),
  review: (payload) =>
    req("/api/review", { method: "POST", body: JSON.stringify(payload) }),
  rewrite: (payload) =>
    req("/api/rewrite", { method: "POST", body: JSON.stringify(payload) }),

  listDocuments: () => req("/api/documents"),
  createDocument: (payload) =>
    req("/api/documents", { method: "POST", body: JSON.stringify(payload) }),
  updateDocument: (id, payload) =>
    req(`/api/documents/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteDocument: (id) => req(`/api/documents/${id}`, { method: "DELETE" }),

  getVoiceConfig: () => req("/api/voice-config"),
  updateVoiceConfig: (prompt) =>
    req("/api/voice-config", { method: "PUT", body: JSON.stringify({ prompt }) }),
};
__MAURTEN_EOF__

cat > "frontend/src/components/Documents.jsx" << '__MAURTEN_EOF__'
import { useEffect, useState } from "react";
import { api } from "../api.js";

const CATEGORIES = ["general", "press", "social", "editorial", "retail", "product", "newsletter", "ad"];

const blank = { title: "", category: "general", content: "", active: true };

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [form, setForm] = useState(blank);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setDocs(await api.listDocuments());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function save() {
    if (!form.title.trim() || !form.content.trim()) return;
    setError("");
    try {
      if (editingId) {
        await api.updateDocument(editingId, form);
      } else {
        await api.createDocument(form);
      }
      setForm(blank);
      setEditingId(null);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  function edit(doc) {
    setEditingId(doc.id);
    setForm({ title: doc.title, category: doc.category, content: doc.content, active: doc.active });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function toggle(doc) {
    try {
      await api.updateDocument(doc.id, { active: !doc.active });
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  async function remove(id) {
    if (!confirm("Delete this reference document?")) return;
    try {
      await api.deleteDocument(id);
      if (editingId === id) { setForm(blank); setEditingId(null); }
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="single">
      <div className="pane-label">
        {editingId ? "Edit reference document" : "Add reference document"}
      </div>
      {error && <div className="err">{error}</div>}

      <div className="form-grid">
        <div className="field">
          <span className="pane-label">Title</span>
          <input
            type="text"
            value={form.title}
            placeholder="e.g. Kipchoge Berlin caption"
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </div>
        <div className="field">
          <span className="pane-label">Category</span>
          <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      <div className="field">
        <span className="pane-label">Content</span>
        <textarea
          style={{ minHeight: 160 }}
          value={form.content}
          placeholder="Paste exemplar copy that captures the Maurten voice."
          onChange={(e) => setForm({ ...form, content: e.target.value })}
        />
      </div>

      <div className="controls">
        <label className="toggle">
          <input
            type="checkbox"
            checked={form.active}
            onChange={(e) => setForm({ ...form, active: e.target.checked })}
          />
          Include in model context
        </label>
        {editingId && (
          <button className="reset-btn" onClick={() => { setForm(blank); setEditingId(null); }}>
            Cancel
          </button>
        )}
        <button className="btn" onClick={save} disabled={!form.title.trim() || !form.content.trim()}>
          {editingId ? "Update" : "Add"}
        </button>
      </div>

      <div className="pane-label" style={{ marginTop: 8 }}>
        Corpus ({docs.filter((d) => d.active).length} active / {docs.length} total)
      </div>

      {loading ? (
        <div className="spinner">Loading…</div>
      ) : (
        <div className="doc-list">
          {docs.length === 0 && <div className="empty-text">No documents yet</div>}
          {docs.map((doc) => (
            <div key={doc.id} className={`doc-row ${doc.active ? "" : "inactive"}`}>
              <span className="doc-cat">{doc.category}</span>
              <span className="doc-title">{doc.title}</span>
              <span className="doc-meta">{doc.content.length} chars</span>
              <div className="doc-actions">
                <button className="reset-btn" onClick={() => toggle(doc)}>
                  {doc.active ? "Deactivate" : "Activate"}
                </button>
                <button className="reset-btn" onClick={() => edit(doc)}>Edit</button>
                <button className="reset-btn" onClick={() => remove(doc.id)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
__MAURTEN_EOF__

cat > "frontend/src/components/Reviewer.jsx" << '__MAURTEN_EOF__'
import { useEffect, useState } from "react";
import { api } from "../api.js";

const INTENT_LABELS = {
  product: "Product-led",
  reactive: "Reactive moment",
  athlete: "Athlete story",
  education: "Education",
  brand: "Brand / awareness",
};
const FORMAT_LABELS = {
  general: "Any format",
  pdp: "Product page (PDP)",
  newsletter: "Newsletter",
  social: "Social / SoMe",
  ad: "Ad copy",
  press: "Press release",
  retail: "Retail guide",
  editorial: "Editorial / long-form",
};

export default function Reviewer() {
  const [copy, setCopy] = useState("");
  const [format, setFormat] = useState("general");
  const [intent, setIntent] = useState("product");

  const [review, setReview] = useState(null);
  const [rewrite, setRewrite] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [error, setError] = useState("");

  // Confirm the API is reachable; harmless if it fails.
  useEffect(() => {
    api.options().catch(() => {});
  }, []);

  async function runReview() {
    if (!copy.trim()) return;
    setLoading(true);
    setError("");
    setReview(null);
    setRewrite(null);
    try {
      const r = await api.review({ copy, format, intent });
      setReview(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function runRewrite() {
    if (!review) return;
    setRewriting(true);
    setError("");
    try {
      const issues = review.notes
        .filter((n) => n.flag === "red" || n.flag === "amber")
        .map((n) => `${n.issue}${n.fix ? ` Fix: ${n.fix}` : ""}`);
      const r = await api.rewrite({ copy, format, intent, issues });
      setRewrite(r.rewrite);
    } catch (e) {
      setError(e.message);
    } finally {
      setRewriting(false);
    }
  }

  function reset() {
    setCopy("");
    setReview(null);
    setRewrite(null);
    setError("");
  }

  const score = review?.score ?? 0;
  const col = score >= 8 ? "var(--green)" : score >= 5 ? "var(--amber)" : "var(--red)";
  const reds = review?.notes.filter((n) => n.flag === "red") || [];
  const ambers = review?.notes.filter((n) => n.flag === "amber") || [];
  const greens = review?.notes.filter((n) => n.flag === "green") || [];

  return (
    <div className="layout">
      <div className="pane pane-left">
        <div className="pane-label">Draft copy</div>
        <textarea
          id="input"
          placeholder="Paste draft copy here."
          value={copy}
          onChange={(e) => setCopy(e.target.value)}
        />
        <div className="selects">
          <select value={format} onChange={(e) => setFormat(e.target.value)}>
            {Object.entries(FORMAT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <select value={intent} onChange={(e) => setIntent(e.target.value)}>
            {Object.entries(INTENT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div className="controls">
          <span className="char-count">{copy.length} chars</span>
          <button className="btn" onClick={runReview} disabled={loading || !copy.trim()}>
            {loading ? "Reviewing…" : "Review"}
          </button>
        </div>
      </div>

      <div className="pane">
        <div className="pane-label">Editorial notes</div>

        {error && <div className="err">{error}</div>}

        {!review && !loading && !error && (
          <>
            <div className="step-label">
              1. Paste copy. Select <span>format</span> + <span>intent</span>.
              <br />2. Hit <span>Review</span>.
              <br />3. Get a verdict, notes, and an optional <span>rewrite</span>.
            </div>
            <div className="empty">
              <div className="empty-mark">—</div>
              <div className="empty-text">Awaiting results</div>
            </div>
          </>
        )}

        {loading && <div className="spinner">Reviewing against the Maurten voice…</div>}

        {review && (
          <>
            <div className="verdict">
              <div className="verdict-dot" style={{ background: col }} />
              <div>
                <div className="verdict-score" style={{ color: col }}>
                  {score}
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>/10</span>
                </div>
                <div className="verdict-sub">Voice score</div>
              </div>
              <div className="verdict-text">{review.verdict}</div>
            </div>

            <div className="notes">
              {reds.length > 0 && <div className="divider">Red lines</div>}
              {reds.map((n, i) => <Note key={`r${i}`} n={n} />)}
              {ambers.length > 0 && <div className="divider">Voice notes</div>}
              {ambers.map((n, i) => <Note key={`a${i}`} n={n} />)}
              {greens.length > 0 && <div className="divider">What's working</div>}
              {greens.map((n, i) => <Note key={`g${i}`} n={n} />)}
            </div>

            <div className="action-row">
              <button className="reset-btn" onClick={reset}>New review</button>
              <button className="btn-sec" onClick={runRewrite} disabled={rewriting}>
                {rewriting ? "Rewriting…" : "Rewrite"}
              </button>
            </div>

            {rewrite && (
              <>
                <div className="rewrite-label">Rewrite</div>
                <div className="rewrite-box">{rewrite}</div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Note({ n }) {
  return (
    <div className={`note ${n.flag}`}>
      <span className="tag">{n.type}</span>
      <div>
        {n.quote && <div className="note-quote">"{n.quote}"</div>}
        <div className="note-text">{n.issue}</div>
        {n.fix && <div className="note-fix">Try: {n.fix}</div>}
      </div>
    </div>
  );
}
__MAURTEN_EOF__

cat > "frontend/src/components/VoiceConfig.jsx" << '__MAURTEN_EOF__'
import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function VoiceConfig() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getVoiceConfig()
      .then((c) => setPrompt(c.prompt))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setError("");
    setSaved(false);
    try {
      const c = await api.updateVoiceConfig(prompt);
      setPrompt(c.prompt);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="single">
      <div className="pane-label">Core voice instructions (system prompt)</div>
      <div className="step-label">
        This is the persona the model adopts on every review and rewrite. Active
        reference documents are appended automatically as voice examples.
      </div>
      {error && <div className="err">{error}</div>}
      {loading ? (
        <div className="spinner">Loading…</div>
      ) : (
        <>
          <textarea
            style={{ minHeight: 360 }}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <div className="controls">
            {saved && <span className="saved">Saved</span>}
            <button className="btn" onClick={save} disabled={!prompt.trim()}>
              Save
            </button>
          </div>
        </>
      )}
    </div>
  );
}
__MAURTEN_EOF__

cat > "frontend/src/main.jsx" << '__MAURTEN_EOF__'
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
__MAURTEN_EOF__

cat > "frontend/src/styles.css" << '__MAURTEN_EOF__'
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --black: #0a0a0a; --white: #f5f4f0; --mid: #1e1e1e; --border: #2e2e2e;
  --accent: #e8e0d0; --red: #c84b2f; --amber: #c88c2f; --green: #4a8c5c;
  --muted: #6a6a6a; --mono: 'DM Mono', monospace; --sans: 'DM Sans', sans-serif;
}

html, body, #root {
  background: var(--black); color: var(--white); font-family: var(--sans);
  font-size: 13px; line-height: 1.5; -webkit-font-smoothing: antialiased; min-height: 100%;
}

.header {
  padding: 18px 24px 14px; border-bottom: 1px solid var(--border);
  display: flex; align-items: baseline; gap: 12px;
}
.header-logo { font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em; color: var(--muted); }
.header-divider { color: var(--border); }
.header-title { font-size: 13px; font-weight: 400; }
.header-tag {
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--muted); margin-left: auto; border: 1px solid var(--border); padding: 2px 6px;
}

.nav { display: flex; gap: 0; border-bottom: 1px solid var(--border); }
.nav button {
  background: none; border: none; border-bottom: 2px solid transparent; color: var(--muted);
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 12px 24px; cursor: pointer; transition: color 0.15s, border-color 0.15s;
}
.nav button:hover { color: var(--accent); }
.nav button.active { color: var(--white); border-bottom-color: var(--accent); }

.layout { display: grid; grid-template-columns: 1fr 1fr; min-height: 520px; }
@media (max-width: 880px) { .layout { grid-template-columns: 1fr; } }
.pane { padding: 20px 24px; display: flex; flex-direction: column; gap: 10px; }
.pane-left { border-right: 1px solid var(--border); }
.pane-label { font-family: var(--mono); font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }

textarea {
  width: 100%; background: var(--mid); border: 1px solid var(--border); color: var(--white);
  font-family: var(--sans); font-size: 12px; line-height: 1.7; padding: 14px; resize: vertical;
  outline: none; transition: border-color 0.15s;
}
textarea::placeholder { color: var(--muted); font-style: italic; }
textarea:focus { border-color: var(--accent); }
#input { min-height: 200px; }

input[type="text"] {
  width: 100%; background: var(--mid); border: 1px solid var(--border); color: var(--white);
  font-family: var(--sans); font-size: 12px; padding: 9px 12px; outline: none;
}
input[type="text"]:focus { border-color: var(--accent); }

.selects { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
select {
  background: var(--mid); border: 1px solid var(--border); color: var(--white);
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.04em; padding: 7px 9px;
  outline: none; cursor: pointer; width: 100%;
}
select option { background: var(--mid); }

.controls { display: flex; align-items: center; gap: 8px; }
.char-count { font-family: var(--mono); font-size: 9px; color: var(--muted); }

.btn {
  background: var(--white); color: var(--black); border: none; font-family: var(--mono);
  font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; padding: 8px 18px;
  cursor: pointer; transition: background 0.15s; margin-left: auto; white-space: nowrap;
}
.btn:hover { background: var(--accent); }
.btn:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-sec {
  background: var(--mid); color: var(--accent); border: 1px solid var(--border);
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase;
  padding: 8px 14px; cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.btn-sec:hover { border-color: var(--accent); }
.btn-sec:disabled { opacity: 0.3; cursor: not-allowed; }

.err { font-family: var(--mono); font-size: 9px; color: var(--red); padding: 6px 8px; border: 1px solid var(--red); }

.step-label { font-family: var(--mono); font-size: 9px; letter-spacing: 0.08em; color: var(--muted); padding: 8px 10px; border: 1px solid var(--border); line-height: 1.9; }
.step-label span { color: var(--accent); }
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; min-height: 160px; gap: 8px; color: var(--muted); }
.empty-mark { font-size: 24px; opacity: 0.12; font-family: var(--mono); }
.empty-text { font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; }

.verdict { display: flex; align-items: center; gap: 12px; padding: 10px 14px; border: 1px solid var(--border); margin-bottom: 2px; }
.verdict-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.verdict-score { font-family: var(--mono); font-size: 18px; font-weight: 300; }
.verdict-sub { font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); }
.verdict-text { font-size: 11px; line-height: 1.5; margin-left: auto; max-width: 55%; text-align: right; color: var(--accent); }

.notes { display: flex; flex-direction: column; gap: 2px; }
.note { border-left: 2px solid transparent; padding: 9px 12px; background: var(--mid); display: grid; grid-template-columns: auto 1fr; gap: 6px 10px; align-items: start; }
.note.red { border-left-color: var(--red); }
.note.amber { border-left-color: var(--amber); }
.note.green { border-left-color: var(--green); }
.tag { font-family: var(--mono); font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; padding: 2px 4px; border: 1px solid; white-space: nowrap; margin-top: 2px; }
.red .tag { color: var(--red); border-color: var(--red); }
.amber .tag { color: var(--amber); border-color: var(--amber); }
.green .tag { color: var(--green); border-color: var(--green); }
.note-quote { font-family: var(--mono); font-size: 10px; color: var(--muted); margin-bottom: 3px; font-style: italic; }
.note-text { font-size: 12px; line-height: 1.5; color: var(--accent); }
.note-fix { font-size: 11px; color: var(--green); margin-top: 4px; font-family: var(--mono); font-style: italic; }
.divider { font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); padding: 7px 0 4px; border-top: 1px solid var(--border); margin-top: 2px; }

.action-row { display: flex; gap: 8px; margin-top: 4px; }
.reset-btn { background: none; border: 1px solid var(--border); color: var(--muted); font-family: var(--mono); font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; padding: 5px 10px; cursor: pointer; }
.reset-btn:hover { border-color: var(--accent); color: var(--accent); }

.rewrite-label { font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); margin-top: 8px; }
.rewrite-box { background: var(--mid); border: 1px solid var(--green); padding: 14px 16px; font-size: 13px; line-height: 1.8; color: var(--accent); white-space: pre-wrap; margin-top: 6px; }

.spinner { font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); padding: 8px 0; }

/* Documents + voice config */
.single { padding: 24px; display: flex; flex-direction: column; gap: 16px; max-width: 920px; }
.doc-list { display: flex; flex-direction: column; gap: 6px; }
.doc-row { background: var(--mid); border: 1px solid var(--border); padding: 12px 14px; display: flex; align-items: center; gap: 12px; }
.doc-row.inactive { opacity: 0.5; }
.doc-cat { font-family: var(--mono); font-size: 8px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); border: 1px solid var(--border); padding: 2px 6px; white-space: nowrap; }
.doc-title { font-size: 13px; flex: 1; }
.doc-meta { font-family: var(--mono); font-size: 9px; color: var(--muted); }
.doc-actions { display: flex; gap: 6px; }
.form-grid { display: grid; grid-template-columns: 1fr 160px; gap: 8px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.toggle { display: flex; align-items: center; gap: 6px; font-family: var(--mono); font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); cursor: pointer; }
.saved { font-family: var(--mono); font-size: 9px; color: var(--green); letter-spacing: 0.08em; text-transform: uppercase; }
__MAURTEN_EOF__

cat > "frontend/vite.config.js" << '__MAURTEN_EOF__'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy /api to the backend in local dev so you don't need CORS locally.
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
__MAURTEN_EOF__

echo "Done — see README.md for local dev + Railway deploy steps."
