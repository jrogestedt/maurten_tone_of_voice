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
# maurten_tone_of_voice
