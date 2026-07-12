# Learn to Teach Agent

AI-assisted technical teaching platform that turns a learning topic, optional notes, and a saved curriculum into a beginner-friendly article, teaching example, interactive quiz, and publication-readiness report — then hosts the published blog on the same FastAPI app.

## Product problem

Engineers learning a long path (FastAPI → Docker → Kubernetes → LLM inference → vLLM → RAG → Prometheus/Grafana) accumulate notes that rarely become durable teaching artifacts. Generic LLM wrappers invent personal war stories, fake metrics, and ungrounded commands. This project treats generation as a **reviewable draft pipeline** with curriculum tools, deterministic validation, manual approval, and self-hosted publishing.

## Why this is not just an AI text wrapper

- Real LangChain 1.x agent via `create_agent` with tools that load learning path, notes, knowledge packs, and writing profile
- Two generation modes: **notes-grounded** vs **curriculum-aware**
- Deterministic validation after structured output (quiz schema, first-person claims, fabricated metrics, sources)
- Content lifecycle: `needs_review` → `approved` → `published` (no auto-publish)
- Self-hosted public blog + private author dashboard (not Medium/Substack/WordPress)
- Notes stored in PostgreSQL, not only on the container filesystem

## Architecture

```text
Browser
  ├─ Public: / /blog /blog/{slug} /blog/{slug}/quiz
  └─ Admin:  /admin/* (session auth)
        │
        ▼
FastAPI (Jinja2 + JSON API)
  ├─ content_service (lifecycle, slug, publish)
  ├─ validation_service (deterministic checks)
  └─ content_agent (LangChain create_agent)
        ├─ load_learning_path
        ├─ load_topic_notes
        ├─ load_approved_knowledge
        └─ load_writing_profile
        │
        ▼
PostgreSQL (notes + content_items)
```

### Agent tool flow

1. Agent receives topic + optional notes.
2. System prompt requires calling context tools before drafting.
3. Tools return curriculum/notes/knowledge/profile as **untrusted data**.
4. Agent returns `ContentPackage` via `response_format=ContentPackage`.
5. Validation layer records warnings and blocks invalid quiz/source schemas.
6. App persists status `needs_review` for human edit/approve/publish.

### Notes-grounded vs curriculum-aware

| Mode | When | Behavior |
|------|------|----------|
| `notes_grounded` | Meaningful notes present | May use author's stated observations; must not invent extra personal experiences |
| `curriculum_aware` | Notes missing/weak | Neutral article from learning path + knowledge pack + writing profile; no fabricated "I debugged…" stories; hypotheticals use Imagine/Suppose/Consider |

## Prompt-engineering design

Prompts live under `prompts/` with version, role, goal, context/source/personal-experience policies, teaching/voice requirements, output contract, failure behavior, and self-check. Notes/knowledge files cannot override the system prompt. See `prompts/README.md`.

## Local development

### Prerequisites

- Python 3.12
- Docker / Docker Compose
- Optional: kubectl for manifest dry-run validation

### Setup

```bash
cp .env.example .env
# Set OPENAI_API_KEY or ANTHROPIC_API_KEY, ADMIN_USERNAME, ADMIN_PASSWORD_HASH, SESSION_SECRET
# For Compose .env files, escape each bcrypt $ as $$
python3 -m venv .venv
source .venv/bin/activate
make install
```

Generate an admin password hash:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode().replace('\$','\$\$'))"
```

Store the plaintext password only in a local secret manager or `.admin_credentials.local` (gitignored). Never commit `admin` / `changeme` defaults for a running environment.

### Run tests and lint

```bash
make lint
make test
```

All LLM-dependent tests mock the model. CI does not require API keys.

### Run with Docker Compose

```bash
cp .env.example .env
# optionally set OPENAI_API_KEY or ANTHROPIC_API_KEY + LLM_PROVIDER
make up
make smoke
```

Compose starts:

- `db` — PostgreSQL 16 with named volume `pgdata` and `pg_isready` health check
- `app` — FastAPI/Uvicorn on `8000`, waits for healthy DB, loads `.env`

### Persistence check (documented procedure)

1. Log into `/admin`, create a note and a draft (or insert via tests).
2. Recreate only the app container: `docker compose up -d --force-recreate --no-deps app`
3. Confirm the note and draft still exist in `/admin` (data lives in the Postgres volume).

## API usage example

```bash
# Login is cookie-based for HTML; for JSON API use an authenticated session.
# After browser login, or in tests with TestClient session:

curl -X POST http://localhost:8000/api/v1/content/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "Docker",
    "notes": "",
    "audience": "engineers preparing for production LLM inference",
    "content_type": "tutorial",
    "tone": "clear, practical, beginner-friendly",
    "desired_length": "medium",
    "include_quiz": true
  }'
```

Health (no LLM call):

- `GET /health/live`
- `GET /health/ready` — DB + config only

## Docker

Multi-stage-style slim Python 3.12 image:

- Dependency layer caching via `requirements.txt`
- Non-root user `appuser` (uid 10001)
- No API keys baked into the image
- Port 8000, Uvicorn, container health check
- `.dockerignore` excludes `.env` and tests

## Kubernetes (educational / local cluster)

Manifests under `k8s/`:

| Resource | Purpose |
|----------|---------|
| `namespace.yaml` | Isolate resources |
| `app-configmap.yaml` | Non-secret config |
| `app-secret.example.yaml` | Placeholder secrets only |
| `app-deployment.yaml` | 2 replicas, probes, resources, non-root |
| `app-service.yaml` | ClusterIP port 80 → 8000 |
| `dev-postgres.yaml` | Dev-only Postgres + PVC |

Validate client-side:

```bash
make k8s-validate
```

Local cluster sketch (Docker Desktop / Minikube / Kind):

1. Build image: `docker build -t learn-to-teach-agent:local .`
2. Copy `app-secret.example.yaml` → `app-secret.yaml`, fill placeholders
3. `kubectl apply -f k8s/namespace.yaml -f k8s/dev-postgres.yaml -f k8s/app-configmap.yaml -f k8s/app-secret.yaml -f k8s/app-deployment.yaml -f k8s/app-service.yaml`

**Not claimed:** this repository's verification did not deploy to a live Kubernetes cluster unless separately performed. Production should use managed PostgreSQL, not `dev-postgres.yaml`.

## Domain / hosting outline

1. Deploy the Dockerized app behind a reverse proxy.
2. Set `PUBLIC_BASE_URL` to your public origin.
3. Add a custom domain at your host.
4. Create DNS CNAME or A record.
5. Terminate HTTPS at the proxy/load balancer.
6. Verify published articles at `/blog/{slug}`.

Domain configuration is **not** claimed completed in this project verification.

## Database note

MVP creates tables with SQLAlchemy `create_all` on startup. Alembic migrations are a recommended production improvement.

## Security limitations

- Single-admin session auth (bcrypt hash + HTTP-only cookie). Prefer a managed IdP before multi-user.
- Do not commit real API keys or production password hashes you care about.
- Uploaded notes are untrusted; size-limited; `.txt`/`.md` only.
- Rendered Markdown is sanitized with Bleach (no author JS in articles).

## AI-content limitations

- Model output can still be wrong; human review is mandatory.
- Validation catches many claim classes but not all factual errors.
- Knowledge packs are local and incomplete by design.

## What was actually validated

See the final verification report in the project completion notes / CI logs for exact commands. Intended verification set:

- `ruff check`
- `pytest`
- `docker compose config`
- `docker compose up -d --build`
- `scripts/smoke_test.sh`
- Admin login, note create, approve/publish lifecycle, public 200/404, app recreate persistence
- `kubectl` client dry-run when available

## Future improvements

- Alembic migrations
- Managed auth and multi-author roles
- Richer knowledge packs per curriculum topic
- Background job queue for long generations
- Managed Postgres + object storage for uploads

## Résumé-ready description

Built a FastAPI + LangChain portfolio platform that generates curriculum-aware technical teaching content with tool-grounded context, deterministic safety validation, PostgreSQL-backed drafts/notes, interactive quizzes, and a self-hosted publish workflow packaged with Docker Compose and educational Kubernetes manifests.

## Interview talking points

1. Why `create_agent` + tools beats a single LLM call for grounded teaching content
2. How notes-grounded vs curriculum-aware prevents fabricated experience claims
3. Why validation is deterministic and separate from the model
4. Content lifecycle and why auto-publish is unsafe
5. How Compose health checks and named volumes demonstrate real ops basics
6. What would change for production (migrations, managed DB, IdP, secrets)

## Exact next commands for a real LLM generation

```bash
cp .env.example .env
# Edit .env: set LLM_PROVIDER, MODEL_NAME, and the matching API key
make up
# Open http://localhost:8000/admin/login with your configured admin credentials
# Create or select notes → Generate → Edit → Approve → Publish
# Visit http://localhost:8000/blog/{slug}
```
