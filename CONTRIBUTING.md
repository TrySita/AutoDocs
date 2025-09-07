**Welcome**

- Thanks for your interest in improving AutoDocs. This guide explains how to set up your environment, run the stack, make changes safely, and submit high‑quality pull requests.

**Code of Conduct**

- Be respectful and constructive. All participation is governed by `CODE_OF_CONDUCT.md`. Report unacceptable behavior per that document.

**Ways To Contribute**

- Bugs: open issues with repro steps and logs; propose a fix if possible.
- Features: start with an issue to discuss scope; align on UX/API before building.
- Performance/Infra: profiling, caching, CI, and DX improvements welcome.

**Repo Overview**

- `ingestion/`: Python 3.13 FastAPI service, AST parsing (tree‑sitter), graph build, embeddings, semantic/FTS search, job orchestration.
- `webview/`: Turborepo with Next.js App Router app in `apps/webapp` and shared package in `packages/shared` (DB schema, types, tools).
- `docker-compose.yml`: Local Postgres + API + Web.
- `tools/`: helper scripts (`build_all.sh`, `dev.sh`).
- `ingested_repos/`: Local workspace for cloned repos and per‑repo SQLite DBs.

**Prerequisites**

- Node 20+ and pnpm 10+ (Corepack is fine). Install: `corepack enable && corepack prepare pnpm@10.15.0 --activate`.
- Python 3.13 with `uv`. Install: see https://docs.astral.sh/uv/
- Docker + Docker Compose.

**Development**

- Copy `.env.local.example` file and fill keys you have:
  - `cp .env.local.example .env.local`
  - DB URLs are prefilled for Docker Compose; adjust if needed.
  - Ensure your `ANALYSIS_DB_URL` points to the right **absolute** path.
- Install/build everything (optional, required for local dev):
  - `./tools/build_all.sh`
  - Python: syncs `ingestion` via `uv` (and exports `requirements_lock.txt`).
  - TypeScript: installs and builds `webview` via pnpm + Turbo.

**Run Locally**

- Dev loop (DB + API + Web with hot-reload):
  - `./tools/dev.sh`
- With Docker Compose (prod‑like):

```bash
docker compose build
docker compose up
```
  - Web UI: http://localhost:3000
  - API (FastAPI): http://localhost:8000

**Database Migrations (Drizzle ORM)**

- Source of truth: `webview/packages/shared/src/db/migrations/schema.ts` ( + `relations.ts`).
- Apply to local Postgres (after services are up):
  - `cd webview/packages/shared`

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```
- Commit any changed files under `webview/packages/shared/src/db/migrations/` along with schema/relations updates.

**API Schema → TypeScript Types**

- When FastAPI endpoints change, regenerate client types for the web app:
  - `cd webview/apps/webapp`
  - `pnpm generate-api-types` (reads `http://localhost:8000/schema` into `src/types/api.ts`)

**Coding Standards**

- TypeScript (webview):
  - Lint: `cd webview && pnpm lint` (Next + ESLint flat config).
  - Format: `pnpm format` (Prettier). Keep imports tidy; prefer named exports.
  - App structure: see `webview/apps/webapp/AGENTS.md` for conventions (components, hooks, tRPC, routes).
- Python (ingestion):
  - Install deps: `cd ingestion && uv sync`
  - Lint: `uv run ruff check .`
  - Format (ruff formatter): `uv run ruff format .`
  - Types: `uv run basedpyright` (uses root `pyrightconfig.json`).
  - Target 3.13; keep imports explicit and functions small/cohesive.

**Tests**

- Python (pytest):
  - `cd ingestion && uv run pytest -q`
  - Write fast unit tests under `ingestion/tests/` (uses `tool.pytest.ini_options`).
- TypeScript: no runner is configured yet. If you add tests, colocate as `*.test.ts(x)` or under `__tests__/`, and include a matching `pnpm test` script in the touched package.

**Before You Commit**

- Env: `cp .env.example .env` exists and keys are set for any LLM features you touched.
- Build: `./tools/build_all.sh` succeeds locally.
- Lint/format:
  - `cd webview && pnpm lint && pnpm format:check`
  - `cd ingestion && uv run ruff check . && uv run basedpyright && uv run ruff format --check .`
- Tests: `cd ingestion && uv run pytest -q` passes. Add/adjust tests for your change.
- DB: If schema changed, run Drizzle push locally and commit updated migration/schema files.
- Types: If API changed, run `pnpm generate-api-types` and commit the updated types.

**Commit & PR Guidelines**

- Commits: short, imperative subject; optional Conventional Commits style (e.g., `feat:`, `fix:`, `refactor:`). Group related changes.
- PRs: include summary, validation steps, screenshots for UI, list of env vars/migrations touched, and any follow‑ups.
- CI: GitHub Actions workflow `build-all.yml` runs `tools/build_all.sh` on PRs. Ensure it passes.

**Security & Secrets**

- Never commit secrets. Use `.env` (Docker Compose mounts it as a secret) and Cloud provider secret stores in production.
- Keep PII out of logs and fixtures. Scrub any sample data.

**Troubleshooting**

- Web cannot reach API: ensure `INGESTION_API_URL=http://localhost:8000` in `.env` and web dev server restarted.
- Missing `uv`/`pnpm`: install per prerequisites or run `tools/build_all.sh --skip-uv` / `--skip-ts` to narrow scope.
- Ingestion README mentions Poetry; current tooling uses `uv`. Prefer `uv` commands in this repo.

**Release & Versioning**

- No formal release automation yet. For user‑visible changes, update `README.md` and migration notes where relevant.

**Questions**

- Open an issue with your question and context, or start a draft PR to discuss design/code early.

Thanks again for contributing!
