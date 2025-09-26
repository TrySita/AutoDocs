![Sita Github Banner](https://raw.githubusercontent.com/TrySita/AutoDocs/refs/heads/main/assets/sita-og.png)

## Follow Us
- **Sohan** - [@SohanSarabu](https://x.com/SohanSarabu)
- **Adi** - [@adiperswal](https://x.com/adiperswal)

<div align="center">
   <div>
      <a href="https://docs.trysita.com"><strong>Docs</strong></a> ·
      <a href="https://github.com/TrySita/AutoDocs/issues"><strong>Report Bug</strong></a> ·
      <a href="https://langfuse.com/ideas"><strong>Feature Request</strong></a> ·
   </div>
   <br/>
   <span>Sita uses <a href="https://github.com/orgs/TrySita/discussions"><strong>GitHub Discussions</strong></a>  for Support and Feature Requests.</span>
   <br/>
   <br/>
   <br/>
   <div>
   </div>
</div>

<p align="center">
   <a href="./LICENSE">
   <img src="https://img.shields.io/badge/License-Apache%202.0-E11311.svg" alt="Apache 2.0 License">
   </a>
</p>

<p align="center">
  <a href="./readmes/README.zh-CN.md"><img alt="Español" src="https://img.shields.io/badge/Español-d9d9d9"></a>
  <a href="./readmes/README.zh-CN.md"><img alt="हिन्दी" src="https://img.shields.io/badge/Hindi-d9d9d9"></a>
    <a href="./readmes/README.zh-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
</p>

<video width="640" controls>
 <source src="https://github.com/TrySita/AutoDocs/raw/refs/heads/main/assets/sita%20demo.mp4" type="video/mp4">
 Your browser does not support the video tag.
</video>

# AutoDocs, by [Sita](https://trysita.com)

Automate documentation for any repo: we traverse your codebase, parse the AST, build a dependency graph, and walk that graph to generate accurate, high-signal docs. A built-in MCP server lets coding agents deep-search your code via HTTP.

(Interested in our hosted or enterprise offerings? Join the waitlist at https://trysita.com)

## What This Repo Does

- Parses your repository using [tree-sitter](https://github.com/tree-sitter/tree-sitter) (AST parsing) and SCIP (symbol resolution).
- Constructs a code dependency graph (files, definitions, calls, imports) and topologically sorts the dependencies.
- Traverses that graph to create repository-wide, dependency-aware documentation and summaries.
- Exposes a FastAPI backend for ingestion/search and a Next.js web UI for chat and exploration.
- Provides an MCP server so agentic tools can query your repo with deep search.

---

## Prerequisites

Install these once on your machine:

- pnpm 10+ (Node 20+ recommended; Corepack is fine). [Docs](https://pnpm.io/installation)
- uv (fast Python package manager). [Docs](https://docs.astral.sh/uv/)
- Docker + Docker Compose (to run everything locally). [Docs](https://docs.docker.com/engine/install/)

Reference docs

- pnpm install: https://pnpm.io/installation
- uv install: https://docs.astral.sh/uv/

## GitHub Personal Access Token (optional)

Some features or scripts may call the GitHub API (e.g., fetching repo metadata). If you hit rate limits or need to access private repos, create a Personal Access Token (PAT) and set it in your environment.

- How-to (official docs): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
- Create fine-grained PAT (recommended): https://github.com/settings/personal-access-tokens/new
- Create classic PAT (legacy): https://github.com/settings/tokens/new

Suggested scopes

- Public repos only: use a fine-grained token with selected repositories (read-only) or a classic token with `public_repo`.
- Private repos: fine-grained token with read-only repo access to the needed repositories, or a classic token with `repo`.

Add to your `.env` (or shell env):

```bash
GITHUB_TOKEN=ghp_your_token_here
```

Notes

- Keep this token secret; do not commit `.env`.
- Fine-grained tokens are preferred for tighter, per-repo permissions.

## Quickstart (copy/paste)

1. Environment

```bash
cp .env.example .env
```

### Configuration

#### Preconfigured

- Database: `DATABASE_URL` (local postgres DB). In Compose, DB is available at `postgresql://postgres:postgres@db:5432/app`.
- Ingestion API: `INGESTION_API_URL` for the web app to call the FastAPI service.
- Analysis storage: `ANALYSIS_DB_DIR` controls where generated per-repo SQLite files live.

---

#### To-be configured

- Summaries: `SUMMARIES_API_KEY`, `SUMMARIES_MODEL`, `SUMMARIES_BASE_URL` (OpenAI-compatible, default [OpenRouter](https://openrouter.ai/))
- Embeddings: `EMBEDDINGS_API_KEY`, `EMBEDDINGS_MODEL`, `EMBEDDINGS_BASE_URL` (OpenAI-compatible, default [OpenAI](https://openai.com/api/))
- Rate limiting: `MAX_REQUESTS_PER_SECOND` for LLM summary batching (default 15)

---

2. Run locally with Docker Compose

```bash
docker compose up -d

# If you want to see logs
docker compose up
```

You should now have:

- Web UI at http://localhost:3000
- API at http://localhost:8000 (OpenAPI schema at `/schema`)

## Updating Docs

To refresh a repository’s docs after code changes, remove the repo and re-ingest it (temporary workflow):

- UI: delete the repo in your Workspace, then add it again (ingestion starts automatically).

We’re actively adding a one-click "Resync" button in the UI, followed by automatic periodic ingestion (coming soon)

## Using the MCP Server

The MCP server is available at `http://localhost:3000/api/mcp` and is designed for coding agents and MCP-compatible clients. It exposes a `codebase-qna` tool that answers repository-scoped questions by querying the analysis databases that AutoDocs produces.

Tips

- Point your MCP client at `http://localhost:3000/api/mcp`.
- Include an `x-repo-id` header with the repo ID (you can find it in the UI).
- For setup guides with popular tools (Claude, Cursor, Continue), see https://docs.trysita.com

## Development Workflow (for contributing)

For a local dev loop without Docker Compose you can run the API and web dev servers directly:

```bash
# concurrent dev (API + Web + DB)
./tools/dev.sh --sync
```

Database migration (run if modifying the postgres schema)

```bash
cd packages/shared
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app pnpm drizzle-kit push --config drizzle.main.config.ts
```

## Project Layout

- `ingestion/` — Python FastAPI service, AST parser, graph builder, embeddings, and search.
- `webview/` — Next.js app (Turborepo workspace) and shared TS packages.
- `docker-compose.yml` — local Postgres, API, and Web services.
- `tools/` — helper scripts (`build_all.sh`, `dev.sh`, `uv_export_requirements.sh`).

## Troubleshooting

- Web can’t reach the API: ensure `INGESTION_API_URL=http://api:8000` is set in `.env`.
- Missing `uv`/`pnpm`: install them (see links above)

## Known Issues

- In your repositories, code must live at the repository root, not in a nested folder.
- Language support: currently supports TS, JS, and Python; currently working on expansion to Go, Kotlin, Java, and Rust.
- Polyglot repos (multiple languages in one repo): not supported yet, but we’re actively working on it.

## License

Licensed under the Apache 2.0 License. See [LICENSE](./LICENSE).
