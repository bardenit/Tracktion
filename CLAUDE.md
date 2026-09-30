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

## Release: build and publish images

Run this after any change that should reach the server. Do it every time a build is
successfully updated.

`docker-compose.yml` has **no `build:` sections** — it pulls `jbarden75/tracktion-backend:latest`
and `jbarden75/tracktion-frontend:latest` from Docker Hub. So `docker-compose up --build` does
nothing useful locally; the images must be built and pushed, and the Proxmox VM then pulls them.

**Target is `linux/amd64` only.** The dev Mac is arm64, so a plain `docker build` produces an
arm64 image that will not run on the VM. Always pass `--platform linux/amd64`.

```bash
# 1. build both, amd64, loaded into Docker Desktop
docker buildx build --platform linux/amd64 -t jbarden75/tracktion-backend:latest  --load ./backend
docker buildx build --platform linux/amd64 -t jbarden75/tracktion-frontend:latest --load ./frontend

# 2. verify architecture before pushing
docker image inspect jbarden75/tracktion-backend:latest  --format '{{.Os}}/{{.Architecture}}'
docker image inspect jbarden75/tracktion-frontend:latest --format '{{.Os}}/{{.Architecture}}'
# both must print linux/amd64

# 3. smoke-test the backend image: migrations run and /health answers
D=$(mktemp -d)
docker run -d --rm --name tt-smoke --platform linux/amd64 \
  -e DATA_DIR=/app/data -e JWT_SECRET_KEY=smoketest \
  -v $D:/app/data -p 18000:8000 jbarden75/tracktion-backend:latest
sleep 20 && curl -s http://127.0.0.1:18000/health    # {"status":"healthy","database":"ready"}
docker logs tt-smoke | tail -5
docker rm -f tt-smoke

# 4. push
docker push jbarden75/tracktion-backend:latest
docker push jbarden75/tracktion-frontend:latest
```

Then pull and restart on the VM.

Notes:

- The build runs under emulation on Apple Silicon, so `pip install` and `npm install` are slow.
  That is expected, not a hang.
- `docker images` reports a buildx-loaded image's compressed size, so the backend shows ~116 MB
  where a native build of the same Dockerfile shows ~505 MB. Not a truncated image; verify with
  the smoke test rather than by size.
- Pushing these tags replaces the previous multi-arch manifests with amd64-only. That is
  deliberate — the VM is x86 — but nothing on arm64 can pull `:latest` afterwards.

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

## Permission model

Two independent axes. Do not conflate them.

**Account level** — `User.is_admin`, enforced by `require_admin` in `app/deps.py`:

| Admin only | Any authenticated user |
|---|---|
| Create a vehicle (`vehicles.py` `create_vehicle`) | OCR scans, all four routes |
| Delete a vehicle (admin **and** owner) | Everything gated per-vehicle below |
| All of `routes/settings.py`, including OCR provider config | |

**Per-vehicle level** — `VehicleCollaborator.role` (`viewer` / `editor`), enforced by
`check_vehicle_access(..., require_write=True)` at 35 call sites. Editors write fuel,
maintenance, expenses and the rest; viewers read.

Consequences worth keeping in mind:

- Since only admins create vehicles, a vehicle owner is always an admin. The owner check on
  delete is still there for the case of a second admin.
- OCR is deliberately **not** admin-gated: a scan extracts values and writes nothing. Saving
  them goes through the fuel and expense routes, which enforce write access per vehicle. Gating
  the scan would stop an editor filling in a form they are allowed to submit.
- When an action is admin-only, hide the control in the UI rather than letting the user meet a
  403 — see the Add Vehicle button in `VehiclesPage.tsx`.

## Reference

- @CHANGES_OLLAMA_MIGRATION.md — OCR provider design, measured model accuracy, prompt and
  schema rationale. Read before changing any OCR prompt or schema; the wording is tuned
  against measured failure modes and small edits regress it.
- @DEVELOPMENT.md, @SETUP.md — setup and deployment.
