# Tracktion — Project Instructions

Vehicle tracking app. FastAPI + SQLAlchemy backend, React + Vite + Tailwind frontend,
deployed with Docker Compose.

## Build and run: Docker only

**Never run `npm install` in `frontend/` on this machine.** The repo lives on `/Volumes/MAC`,
an external volume, and npm's small-file churn wedges there in uninterruptible I/O wait — 31
minutes with no completion and no error, where the same install on local disk takes 2 seconds.
It does not fail loudly; it hangs.

```bash
docker-compose up -d --build                              # build and run everything
docker-compose exec api python -m alembic upgrade head    # migrations (first run)
docker-compose logs -f api                                # backend logs
```

If a frontend typecheck or build is needed outside a container, copy `package.json`,
`tsconfig*.json`, `index.html` and `src/` to a local-disk scratch directory and run it there.
Do not create `node_modules` in the repo.

## Tests

Backend — no venv is committed; create one on local disk, not on the repo volume:

```bash
cd backend && DATA_DIR=/tmp/tracktion-tests python -m pytest tests/ -q
```

Frontend (inside a container, or a local-disk copy):

```bash
npm run type-check     # tsc --noEmit
npm run test           # vitest run
npm run build          # vite build
```

## Structure

- `backend/app/routes/` — FastAPI routers, one per domain
- `backend/app/services/` — business logic and external integrations
- `backend/alembic/versions/` — migrations; schema changes need one
- `frontend/src/pages/` — page components; `VehicleDetailPage.tsx` is the large one
- `frontend/src/services/api.ts` — the single API client

## Conventions

- Validation of anything a model or external service returns belongs in **code**, not in a
  prompt or a comment. See `backend/app/services/ocr_validation.py`.
- OCR providers (Ollama, Anthropic, OpenAI-compatible) are configured at runtime in Settings
  and stored in `config.json` under `integrations.ocr`. Nothing is hardcoded, and a fallback
  retry accepts a provider **id** only — never a caller-supplied URL, which would make an
  authenticated endpoint an SSRF primitive.
- Expense categories are user-extensible. Do not constrain them to a fixed enum in
  `ExpenseCreate`; the enum applies only to what the OCR model may return.
- OCR output is always an editable pre-fill the user confirms, never a silent write.

## Reference

- @CHANGES_OLLAMA_MIGRATION.md — OCR provider design, measured model accuracy, prompt and
  schema rationale. Read before changing any OCR prompt or schema; the wording is tuned
  against measured failure modes and small edits regress it.
- @DEVELOPMENT.md, @SETUP.md — setup and deployment.
