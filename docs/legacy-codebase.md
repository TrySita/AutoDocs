# Legacy Codebase Documentation

Research date: 2026-06-02

This document records the codebase as it exists now. It is intentionally
descriptive, not aspirational. The companion target design is in
`docs/ideal-codebase.md`.

## Research Method

The research pass expanded the original question into these threads before
source collection:

1. What are the real runtime entry points?
2. Which APIs are active, which are stubs, and which are stale?
3. What schemas exist in Python, TypeScript, SQLite, and Postgres?
4. Which database is authoritative for application metadata?
5. Which database is authoritative for code intelligence?
6. How does a repository move from a GitHub URL to searchable summaries?
7. How are jobs tracked, persisted, retried, and reported?
8. What does `branch` mean today?
9. What does incremental parsing actually use as a change source?
10. Which languages are supported by Tree-sitter today?
11. Which languages are supported by SCIP today?
12. How are Tree-sitter definitions mapped to SCIP symbols?
13. How are references turned into dependency graphs?
14. How are summary batches sorted and parallelized?
15. What exactly is embedded?
16. What is the embedding wire and storage format?
17. What search modes exist?
18. How do uploaded documents enter the system?
19. How are relevant docs surfaced in the UI?
20. What MCP tools exist today?
21. How do the chat and MCP agents search?
22. Which UI components are visible?
23. Which UI components or routes are hidden, unused, or stubs?
24. What does Docker run?
25. What environment variables are required?
26. Which tests reflect current behavior, and which are stale?
27. What code comments contradict runtime behavior?
28. What must be cleaned before building a branch-aware, auth-aware system?

Sources used:

- Primary source: local repository files under `ingestion`, `webview`,
  `docker-compose.yml`, and `tools`.
- Primary external docs for future comparison: GitHub webhook and GitHub App
  documentation, Google Drive API docs, LSP 3.17 spec, MCP spec, pgvector
  docs.
- Secondary external source for MCP design comparison: Cloudflare Code Mode
  blog post.

## Executive Summary

AutoDocs is currently a local-first code intelligence prototype. The active
product flow is:

1. The Next.js workspace UI stores a repository record in a Postgres app DB.
2. The web server calls the FastAPI ingestion service.
3. FastAPI starts an in-memory background job.
4. The job clones or updates the repository into `ANALYSIS_DB_DIR/clones`.
5. The job creates or updates a per-repository SQLite database named
   `<repo_slug>.db`.
6. Tree-sitter extracts definitions for JavaScript, TypeScript, TSX, JSX, and
   Python.
7. SCIP is run for TypeScript/JavaScript and Python to resolve symbols.
8. References are mapped into definition and file dependency graphs.
9. Definition and file summaries are generated with an OpenAI-compatible chat
   API.
10. Those summaries are embedded with an OpenAI-compatible embedding API.
11. Search uses SQLite FTS5 plus sqlite-vec.
12. The Next.js app reads the generated SQLite DB directly through libSQL.
13. Chat and MCP call a shared agent loop that can run parallel semantic
   searches.

The current codebase does not yet implement:

- GitHub user sign-in for code ingestion.
- GitHub App installation-token based repository access.
- Branch selection as an actual clone/index dimension.
- Durable job queueing.
- Webhook-driven update-on-push.
- Google Drive OAuth.
- Drive folder sync.
- LSP-backed indexing.
- A Code Mode MCP server with `search()` and `execute()`.
- Multi-turn autonomous search beyond a small tool-call budget.
- Background refactor/security/catalog agents with persisted findings.

There is also significant drift:

- FastAPI schemas and generated TypeScript OpenAPI types disagree.
- Python SQLAlchemy analysis schema and TypeScript Drizzle SQLite schema
  disagree.
- Several tests target endpoints or models that no longer exist.
- Several routes are active-looking but stubbed.
- Comments mention Turso/Pinecone/embedded replicas where runtime code now uses
  local SQLite and sqlite-vec.

## Repository Shape

Top-level areas:

- `ingestion/`: Python FastAPI service, parser, database models, summaries,
  embeddings, and tests.
- `webview/`: Next.js app plus shared TypeScript package.
- `webview/apps/webapp/`: UI, Next API routes, tRPC routes, local analysis DB
  readers, and UI components.
- `webview/packages/shared/`: Postgres schema, shared database client, shared
  chat/MCP search tools.
- `docker-compose.yml`: Postgres, ingestion API, and web service composition.
- `tools/dev.sh`: local dev orchestrator for Postgres, FastAPI, and Next/Turbo.
- `docs/`: documentation.
- `assets/` and `readmes/`: product media and translated README files.

Generated or runtime-heavy directories exist in the worktree:

- `webview/node_modules`
- `webview/apps/webapp/.next`
- `webview/.turbo`
- `ingestion/.venv`
- `__pycache__` directories

These are not part of the architectural source surface but affect traversal
speed and should be ignored by codebase agents.

## Current Git State Observed

The repository was on branch `docs-ingestion` at the time of exploration.
There were existing user changes in tracked files and untracked Next docs
proxy routes. This document does not revert or normalize those changes.

Dirty tracked files included:

- `ingestion/pyproject.toml`
- `ingestion/src/api/main.py`
- `ingestion/src/api/schemas.py`
- `ingestion/uv.lock`
- `tools/dev.sh`
- `webview/apps/webapp/src/app/layout.tsx`
- `webview/apps/webapp/src/app/workspace/page.tsx`
- `webview/apps/webapp/src/components/workspace/FileExplorer.tsx`
- `webview/apps/webapp/src/components/workspace/NotebookView.tsx`
- `webview/apps/webapp/src/lib/trpc/routes/ingestion.ts`

Untracked active-looking routes:

- `webview/apps/webapp/src/app/api/ingestion/docs/relevant/route.ts`
- `webview/apps/webapp/src/app/api/ingestion/docs/upload/route.ts`

## Runtime Architecture

Current runtime services:

```text
Browser
  |
  v
Next.js web app
  |-- tRPC project/chat/analysis routes
  |-- Next API proxy routes
  |-- MCP route at /api/mcp
  |
  | app metadata
  v
Postgres app DB

Next.js web app
  |
  | ingestion requests, search requests, docs upload/relevance proxy
  v
FastAPI ingestion service
  |
  | clones repos, parses code, generates summaries, generates embeddings
  v
Per-repository SQLite analysis DBs
  |
  | file:// reads through libSQL/Drizzle
  v
Next.js analysis routes and UI
```

The key split is:

- Postgres stores app metadata: projects, users, conversations, messages, auth
  related tables.
- SQLite stores per-repository code analysis: repositories, files, packages,
  definitions, references, dependencies, embeddings, FTS tables, and sqlite-vec
  vectors.

The Next app directly opens the per-repo SQLite database with a `file://` URL
computed from `ANALYSIS_DB_DIR` or repo root. That makes local development
simple, but it means the web server and ingestion service must share the same
filesystem mount.

## FastAPI Surface

Active app: `ingestion/src/api/main.py`.

Active routes:

| Method | Route | Purpose | Notes |
| --- | --- | --- | --- |
| `POST` | `/ingest/github` | Enqueue repository ingestion | Returns only `{ job_id }`. |
| `GET` | `/ingest/jobs/{job_id}` | Poll in-memory job state | Unknown job IDs are returned as succeeded/completed. |
| `POST` | `/search` | Semantic, symbol, path, or hybrid search | Reads `<PATH_TO_DBS>/<repo_slug>.db`. |
| `GET` | `/schema` | Return OpenAPI schema | Intended for TS generation. Generated types are stale. |
| `POST` | `/docs/upload` | Upload docs/PDFs into a repo DB | Converts PDFs to markdown-like text and embeds docs. |
| `POST` | `/docs/relevant` | Find doc-like files relevant to a file/definition | Uses existing target embedding or embeds target text on demand. |
| `POST` | `/repo/delete` | Delete local repo DB and clone | Validates slug and deletes under `ANALYSIS_DB_DIR`. |

Key implementation details:

- CORS currently allows `*` with credentials enabled in `main.py`.
- `/ingest/github` calls `submit_job(run_ingest_job, payload)`.
- `/ingest/jobs/{job_id}` treats missing jobs as successful completion. That
  hides process restarts and invalid job IDs from clients.
- `/search` builds a database path from `PATH_TO_DBS` plus `repo_slug`.
- `/search` requires `EMBEDDINGS_API_KEY` for pure semantic mode. Hybrid mode
  can fall back to FTS if no embedder is configured.
- The route comment says hybrid search is WIP.
- `/docs/upload` stores files as `docs/<relative path>` or converted PDFs as
  `docs/converted/<relative path>.md`.
- `/docs/upload` first tries to embed docs via normal file-summary embeddings;
  if docs have no AI summaries, it falls back to raw content truncated by
  `DOC_EMBED_MAX_CHARS`.
- `/docs/relevant` filters vector neighbors to doc-like paths and languages.

## Pydantic API Schemas

Defined in `ingestion/src/api/schemas.py`.

Important models:

- `IngestRequest`: `github_url`, `repo_slug`, optional `branch`, `force_full`.
- `EnqueueResponse`: only `job_id`.
- `JobStatusResponse`: job state, progress, mode, commit, counters, warnings,
  error, timestamps.
- `SemanticSearchRequest`: `repo_slug`, `query`, mode
  `semantic | symbol | path | hybrid`, `top_k`, optional entity types.
- `UploadDocsResponse`: uploaded/upserted/embedded counts.
- `RelevantDocsRequest`: `repo_slug`, `target_type`, `target_id`, `top_k`.

Schema drift:

- `IngestRequest` docstring still mentions Turso, embedded replicas, sync
  interval, encryption, and deprecated index fields, but the actual model only
  has GitHub URL, slug, branch, and force flag.
- Generated TypeScript OpenAPI types in `webview/apps/webapp/src/types/api.ts`
  still expect `db_path` in `IngestRequest`.
- Generated `EnqueueResponse` includes `status`, but Python returns only
  `job_id`.
- Generated types do not include the newer docs upload/relevance or repo delete
  routes.

## Job Manager

Defined in `ingestion/src/api/job_manager.py`.

Behavior:

- Jobs are stored in a process-local `_jobs` dictionary.
- `submit_job` creates a UUID and schedules `asyncio.create_task`.
- `_run_job` moves status through queued, running, succeeded, failed.
- Progress is mutable in memory.

Operational consequences:

- Jobs disappear on process restart.
- There is no retry queue.
- There is no distributed concurrency control.
- There is no durable event history.
- The web app cannot reliably distinguish "job completed" from "job ID lost"
  because the FastAPI route reports unknown IDs as succeeded.

This is acceptable for a prototype, but it is not enough for update-on-push,
branch fanout, Drive sync, or background agents.

## Repository Ingestion Flow

The worker is `run_ingest_job` in `ingestion/src/api/ingestion.py`.

Phases:

1. `clone`
2. `parse`
3. `summaries`
4. `embeddings`
5. `finalize`

Actual flow:

1. Resolve `WORKDIR` from `ANALYSIS_DB_DIR`, defaulting to `"."`.
2. Clone/update into `WORKDIR/clones/<repo_slug>`.
3. Create/open SQLite DB at `WORKDIR/<repo_slug>.db`.
4. Persist or update one `RepositoryModel`.
5. Run `HybridParser`.
6. Try to read a parse delta.
7. Build definition and file dependency graphs.
8. Run full or incremental summaries.
9. Generate full or incremental embeddings.
10. Count final files/definitions and store current commit hash.

Important drift and bugs:

- `payload.branch` is logged but not passed into `ensure_shallow_main`.
- `ensure_shallow_main` has no branch parameter today.
- Existing clones fetch their current branch rather than a selected branch.
- The worker creates a local `HybridParser`, but then reads delta from global
  `get_parser(db_manager=local_db).current_delta`. Since `HybridParser` creates
  its own `ASTParser`, incremental mode likely never sees the intended delta.
- Because delta is likely missing, the system can fall back to full summary and
  embedding generation.
- `RepositoryModel` is updated by `remote_origin_url`, not by branch or
  snapshot identity.

## Git Utilities

Located in `ingestion/src/ast_parsing/utils/git_utils.py`.

Current behavior:

- Authentication class name suggests GitHub App auth, but it uses a
  `GITHUB_TOKEN` environment variable and pygit2 userpass credentials.
- Public repos can clone without a token.
- `ensure_shallow_main(repo_path, remote_url)` clones shallow and initializes or
  fetches an existing repo.
- The function name and behavior are default/main oriented, but not truly
  branch-aware.
- Changed files are computed from commit diffs and filtered by supported source
  extensions.

For private repository support with user sign-in, this must be replaced or
wrapped by installation-token based GitHub App access.

## Analysis SQLite Schema

Python SQLAlchemy models live in `ingestion/src/database/models.py`.

Tables:

- `repositories`
- `files`
- `packages`
- `definitions`
- `references`
- `imports`
- `definition_dependencies`
- `file_dependencies`
- `embeddings`

Key table properties:

- `repositories` has `repo_slug`, `remote_origin_url`, `commit_hash`, and
  `default_branch`. It has a unique constraint on `(remote_origin_url,
  commit_hash)`, not on branch or repo slug.
- `files` stores `file_path`, `file_content`, `language`, timestamps, AI
  summaries, and has `file_path` unique in a DB.
- `packages` stores package/workspace metadata.
- `definitions` stores name, type, line range, source code, source hash,
  export flags, complexity, and summaries.
- `references` links source definitions to target definitions. Its docstring
  still says "function_calls table".
- `references` has a unique constraint on `(source_definition_id,
  target_definition_id)`, so repeated references from one definition to the
  same target collapse.
- `imports` still exists but is marked "no longer used".
- `definition_dependencies` stores collapsed dependency edges; its check
  constraint includes the misspelling `inheritence`.
- `embeddings` stores raw float32 vector bytes plus metadata. It is unique on
  `(entity_type, entity_id)`.

Runtime virtual tables:

- `definitions_name_fts` using SQLite FTS5.
- `files_path_fts` using SQLite FTS5.
- `embeddings_vec` using sqlite-vec `vec0(embedding float[1536])`.

`DatabaseManager` creates SQLite engines only. Comments still mention
SQLite/Turso and embedded replicas, but runtime code builds `sqlite:///...`
engines.

## App Postgres Schema

The app metadata schema is in
`webview/packages/shared/src/db/migrations/schema.ts`.

The active app DB is Postgres via `DATABASE_URL` or `SUPABASE_DATABASE_URL`.
Important tables include:

- `user`, `session`, `account`, `organization`, `member`, `apikey`, and related
  auth/billing tables.
- `public_projects`: repository catalog shown on `/workspace`.
- `conversations` and `messages`: chat history.
- `anonymous_users`: anonymous user identity records.

`public_projects` fields relevant today:

- `id`
- `name`
- `slug`
- `description`
- `repository_url`
- `is_active`
- `sort_order`
- `db_url`
- `db_key`
- `latest_job_id`
- `latest_job_status`

There are auth-related tables, but current workspace and chat behavior does not
enforce per-user repository permissions.

## TypeScript SQLite Mirror Schema

The web app reads per-repo SQLite DBs with Drizzle schema definitions in
`webview/apps/webapp/src/lib/turso-db/schema.ts`.

This schema is used for reading analysis DBs, not for creating them.

Drift examples:

- TypeScript `repositories` lacks Python's `repo_slug`.
- TypeScript embedding fields do not match Python's current `embeddings`
  requirements.
- Several malformed repeated check constraints appear on unrelated tables.
- The SQLite migration file is fully commented out, so it is not an executable
  schema migration.

This mirror schema should be treated as a generated or manually maintained read
adapter, not as the source of truth.

## SQL vs SQLite Use Cases Today

Current split:

- Postgres: application metadata, public project catalog, users, sessions,
  conversations, messages.
- SQLite: per-repo code intelligence and embeddings.

Why this works for the current prototype:

- One DB file per repo is easy to create, delete, inspect, and mount into both
  ingestion and web.
- SQLite FTS5 and sqlite-vec are enough for local search.
- The web app can open `file://.../<slug>.db` directly.

Why it becomes limiting:

- No durable central branch/snapshot model.
- Filesystem sharing is required between web and ingestion.
- Branch switching cannot be represented cleanly unless every branch gets a
  separate DB or the schema adds a snapshot dimension.
- Multiple users, repo permissions, Drive docs, and background findings need
  central authorization-aware storage.
- Analysis DB schema drift is easy because Python creates the real DB and
  TypeScript hand-writes a read schema.

## File Discovery

Implemented in `ingestion/src/ast_parsing/file_discovery.py` and constants in
`ingestion/src/ast_parsing/constants.py`.

Behavior:

- Recursively lists files.
- Respects `.gitignore`.
- Skips hidden/restricted/common generated directories.
- Uses default ignore patterns such as `node_modules`, `.git`, `.next`,
  `.nuxt`, `dist`, `build`, `.svelte-kit`, `.vscode`, `.idea`, `__pycache__`,
  `.pytest_cache`, `target`, `vendor`, `.gradle`, `.mvn`.

Supported parse extensions today:

- `.js`
- `.jsx`
- `.ts`
- `.tsx`
- `.py`

Many other languages are commented out in `EXTENSIONS`, including Rust, Go, C,
C++, C#, Ruby, Java, PHP, Swift, and Kotlin.

Package files cover more ecosystems than parse support:

- `package.json`
- `requirements.txt`
- `pyproject.toml`
- `Cargo.toml`
- `go.mod`
- `pom.xml`
- `build.gradle`
- `composer.json`
- `Gemfile`
- `Package.swift`

That means package discovery can detect ecosystems the parser cannot actually
analyze.

## Tree-sitter Parsing

Main parser: `ingestion/src/ast_parsing/parser.py`.

Responsibilities:

- Decide full vs incremental parsing.
- Discover files.
- Load required language parsers.
- Extract definitions.
- Persist files, packages, definitions.
- Track parse deltas for added/modified/deleted/renamed files and added
  definitions.

Definition extraction:

- Parser applies a language-specific Tree-sitter query.
- For every supported kind, it looks for captures named `def_<kind>` and
  `name_<kind>`.
- It persists `DefinitionModel` rows with name, line range, source code,
  stripped-comment hash, type, docstring, and default export flag.

Current limitations:

- `tree_imports` and `tree_exports` are initialized but never populated in
  `_parse_file_to_json`.
- `is_default_export` is always `False`.
- JavaScript/JSX query captures use generic `@def` and `@name`, while the
  parser searches for typed captures such as `def_function`; this creates a
  mismatch for JS/JSX extraction.
- TypeScript and Python queries use typed captures and are better aligned with
  the parser.
- Export detection is currently not reliable.
- Import graph tables exist but are not populated by Tree-sitter.

## Package Registry and Monorepo Handling

Package discovery lives under
`ingestion/src/ast_parsing/utils/ts_utils/package_registry.py`.

Capabilities:

- Detect package.json based packages.
- Detect workspace metadata.
- Identify package-based and direct-import monorepo patterns.
- Persist `PackageModel` rows.

Important side effect:

- Some monorepo setup paths create or update root `tsconfig.json` and symlink
  package `node_modules` into the cloned checkout.

This mutation can improve SCIP indexing, but it also means ingestion modifies
the cloned source tree. That is acceptable only if clones are treated as worker
scratch directories and never as pristine source snapshots.

## SCIP Indexing and Mapping

Hybrid parser: `ingestion/src/ast_parsing/hybrid_parser.py`.

SCIP resolver: `ingestion/src/ast_parsing/scip_symbol_resolution.py`.

Symbol mapper: `ingestion/src/ast_parsing/symbol_mapper.py`.

Hybrid flow:

1. Run Tree-sitter first. Tree-sitter is the primary definition source.
2. Detect workspace type.
3. Run SCIP indexing.
4. Extract SCIP symbols.
5. Map Tree-sitter definitions to SCIP symbols.
6. Find SCIP references inside each definition range.
7. Persist local cross-file `ReferenceModel` rows when target definitions can
   be resolved.

SCIP language status:

- TypeScript/JavaScript: `scip-typescript index`.
- Python: `scip-python index .`.
- Go/Rust/Java/C++/.NET/Dart/PHP/Ruby detection exists, but commands are
  commented out and unsupported languages raise `ValueError`.

Mapping strategy:

- Group SCIP symbols by normalized file and start line.
- Match a Tree-sitter definition to a SCIP symbol when there is exactly one
  SCIP symbol on the same start line.
- The docstring says name matching should handle multiple candidates, but the
  implementation currently does not perform that matching.

Reference creation:

- References are attributed to containing definitions by line range.
- Internal references inside the same definition are skipped.
- Same-file references outside the definition and cross-file references can be
  considered dependencies.
- Only outgoing references with a resolved target definition become database
  rows.

## Dependency Graphs and Sorting

Graph builder: `ingestion/src/dag_builder/netx.py`.

Definition graph:

- Nodes are definition IDs.
- Edges are `source_definition_id -> target_definition_id` from `references`.
- Edges are persisted into `definition_dependencies`.

File graph:

- Nodes are file IDs.
- Definition edges are collapsed into file-level dependencies.
- Same-file dependencies are skipped.
- Edges are persisted into `file_dependencies`.

Incremental seed behavior:

- Seeds come from changed file paths and `delta.definitions_added`.
- The code reverse-walks references to collect dependents/ancestors that need
  regenerated summaries.

Summary sorting:

- `ParallelSummaryExecutor.compute_batched_traversal_order` reverses the graph
  so dependencies are processed before dependents.
- It computes strongly connected components.
- It condenses cycles into single SCC nodes.
- It applies transitive reduction.
- It uses topological generations to produce parallelizable levels.

This is the right general idea for dependency-aware summaries, but it depends
on accurate references and a working delta.

## Summary Generation

Files:

- `ingestion/src/ai_analysis/parallel_summaries.py`
- `ingestion/src/ai_analysis/summaries.py`

Client:

- Uses `AsyncOpenAI`.
- Reads `SUMMARIES_API_KEY`.
- Optional `SUMMARIES_BASE_URL`.
- Default model: `google/gemini-2.5-flash`.

Definition summary prompt:

- Includes file ID, file path, definition ID, name, type, source code, direct
  dependency summaries, dependency ID catalog, and sibling definition catalog.
- Requires output with a `<gist>` block and full summary.

File summary prompt:

- Includes raw source, pre-generated definition summaries, definitions catalog,
  connected files catalog, and referenced definitions catalog.
- Prompts for high-level purpose, exports, internal architecture, external
  dependencies, details, and usage guidance.

Limitations:

- Prompts label raw source as TypeScript even for Python or docs.
- `parse_llm_response` assumes `<gist>` and `</gist>` exist and splits directly,
  so malformed model output can break parsing.
- Summary caches are in-memory global dictionaries for a single analysis run.
- Full generation clears caches; incremental generation relies on previous DB
  summaries and cache state.
- Parallel processing is batched and rate-limited, but each level is processed
  sequentially.

## Embeddings

Files:

- `ingestion/src/embeddings/openai_client.py`
- `ingestion/src/embeddings/generator.py`
- `ingestion/src/embeddings/models.py`

Client:

- OpenAI-compatible sync client.
- Reads `EMBEDDINGS_API_KEY`.
- Optional `EMBEDDINGS_BASE_URL`.
- Default model: `text-embedding-3-large`.
- Default dimensions: 1536.

What is embedded:

- File summaries where `FileModel.ai_summary` exists.
- Definition summaries plus name/type where `DefinitionModel.ai_summary`
  exists.
- Uploaded docs can fall back to raw content embedding if summary embedding
  produces zero rows.

Storage format:

- Vectors are packed as float32 with `array("f", vector).tobytes()`.
- Metadata and raw bytes are upserted into `embeddings`.
- The same vectors are mirrored into `embeddings_vec` with rowid equal to the
  `embeddings.id`.

Entity types today:

- `file`
- `definition`

There is no separate first-class `document`, `doc_chunk`, `drive_file`, or
`tag` embedding entity type today.

## Search

Python search: `ingestion/src/embeddings/search.py` and `/search`.

Modes:

- `semantic`: embed the query and search sqlite-vec.
- `symbol`: FTS5 over definition names.
- `path`: FTS5 over file paths.
- `hybrid`: concatenate vector, definition FTS, and path FTS results; dedupe by
  `(entity_type, entity_id)`; keep lowest distance.

Search response:

- `entity_type`
- `entity_id`
- similarity score
- summary text
- metadata including path/language/definition type

Web shared search:

- `webview/packages/shared/src/tools/semantic-search.ts` calls FastAPI `/search`
  with `mode: "semantic"`.
- It then opens the local SQLite DB through libSQL to hydrate files or
  definitions.
- `batchSearchTool.ts` allows 1 to 5 semantic searches to run in parallel.

## Document Upload and Relevant Docs

UI entry points:

- `/workspace` has "Add New Docs".
- File and notebook components expose "Connected Docs" behavior through
  relevant-docs calls.

Next proxy routes:

- `webview/apps/webapp/src/app/api/ingestion/docs/upload/route.ts`
- `webview/apps/webapp/src/app/api/ingestion/docs/relevant/route.ts`

FastAPI routes:

- `/docs/upload`
- `/docs/relevant`

Current behavior:

- User selects a local folder or files in the browser.
- Browser uploads the file bytes to the Next API route.
- Next forwards the `FormData` to FastAPI.
- FastAPI upserts each file into the repo's `files` table.
- Markdown-ish text files are stored under `docs/`.
- PDFs are converted to text/markdown and stored under `docs/converted/`.
- Embeddings are generated for those file rows.
- Relevant docs are retrieved by vector similarity to the selected file or
  definition.

Limitations:

- There is no Google Drive OAuth.
- There is no Drive file ID, folder ID, webViewLink, mime type, revision, or
  permission model.
- There is no document chunking model.
- There are no generated 3-5 tags stored as first-class entities.
- Current document links are file paths inside the local repo DB, not Google
  Docs/Sheets links.

## Next.js Routes and UI

Active pages:

- `/` redirects to `/workspace`.
- Root layout wraps theme, tRPC/query provider, toaster, and theme switcher.
- `/workspace` lists repositories, adds repositories, deletes repositories, and
  uploads docs.
- `/workspace/[repoId]` redirects to `/workspace/[repoId]/docs`.
- `/workspace/[repoId]/docs` renders `UserWorkspace` in docs mode.
- `/workspace/[repoId]/source` renders `UserWorkspace` in source mode.
- Dynamic repo layout stores `repoId` in a Jotai atom.

Workspace shell:

- `UserWorkspace.tsx` renders a horizontal panel group.
- Left panel: `FileExplorer`.
- Main panel: `NotebookView`.
- Optional right panel: `ChatDrawer`.
- Floating chat icon toggles the drawer.
- Command palette searches files and definitions through tRPC FTS routes.

Notebook/docs view:

- File dependency graph.
- File summary.
- Definition cards.
- Definition dependency graph.
- Side-by-side Monaco/docs view.
- Source tab with read-only Monaco and line highlighting.

Active docs features:

- "Add New Docs" upload on workspace page.
- "Connected Docs" calls relevant docs APIs.

Hidden or likely unused code:

- Reingest/Sync button is commented out, but mutation wiring remains.
- Floating outline, old docs/PRs links, and selected package detail view are
  commented out in notebook code.
- `MessageInput.tsx` exists but no imports were found.
- `webview/apps/webapp/src/lib/prompts/MCPPrompt.md` appears stale because the
  active MCP prompt is inline in the shared package.

## tRPC

Root router:

- `projects`
- `analysis`
- `chat`
- `ingestion`

`projects`:

- Lists active `public_projects`.
- Adds a public project.
- Deletes a project and asks FastAPI to delete local analysis artifacts.
- Starts ingestion automatically when adding a project.
- Has reingest mutation even though UI sync button is commented.

Drift:

- `addPublicProject` and `reingestPublicProject` send `db_path` to FastAPI,
  but Python does not define it.
- They cast response to `{ job_id, status }`, but Python returns only
  `{ job_id }`.
- As a result, `latestJobStatus` can be set to `undefined`.

`analysis`:

- Opens local per-repo SQLite DBs via `file://`.
- Uses Drizzle/libSQL to list files, load files by ID/path, load definitions,
  and run FTS searches.

`ingestion`:

- Polls FastAPI job status.

`chat`:

- Streams OpenAI response events through a tRPC subscription.
- Uses an event emitter and the shared agent search loop.

## Chat Persistence

File: `webview/apps/webapp/src/lib/services/messagePersistence.ts`.

Current behavior:

- Uses a single global anonymous user with fingerprint `"global"`.
- Reuses the most recent conversation as a global conversation.
- Does not scope messages by authenticated user or repo.
- `MAX_CHARS_BEFORE_COMPACTION` is 2000.

Risks:

- All users/repos can collapse into one conversation in the current code path.
- Deleting without a conversation ID can delete all conversations.
- This is not compatible with real sign-in or per-repository chat history.

## MCP Server

Route: `webview/apps/webapp/src/app/api/mcp/route.ts`.

Current server:

- Node runtime.
- Streamable HTTP/SSE through `mcp-handler`.
- One tool: `codebase-qna`.
- Tool parameter: `{ question: string }`.
- Repo scope comes from `x-repo-id` header.
- `withMcpAuth` is used only to pass that header into `authInfo.extra.repoId`.
- There is no real token validation, user auth, repo permission check, or
  scoped authorization.

Tool behavior:

- Calls `sendMCPMessage(supabaseDb, question, repoId)`.
- Returns answer text.

This is a working minimal MCP endpoint, but it is the opposite of the target
Cloudflare Code Mode style. It exposes one question-answering tool, not a
typed searchable API with `search()` and `execute()`.

## Agent Search Loop

Shared code:

- `webview/packages/shared/src/tools/sendMCPMessage.ts`
- `webview/packages/shared/src/tools/batchSearchTool.ts`
- `webview/packages/shared/src/tools/semantic-search.ts`

Current agent:

- Uses OpenAI Responses API.
- Model: `gpt-5-mini`.
- Reasoning effort: low.
- Max tool calls: 2.
- Tool list: `batch_search_codebase`.
- `batch_search_codebase` accepts 1 to 5 searches.
- Searches are run in parallel.
- Each search calls FastAPI `/search` in semantic mode.
- Hydration reads the per-repo SQLite DB.

Strengths:

- Parallel search already exists.
- The prompt asks the model to cite paths and symbols.
- The tool budget is small, which controls cost and latency.

Limitations:

- The model cannot read exact file spans through a tool.
- The prompt asks to retrieve targeted spans, but no such tool exists.
- There is no multi-turn planner over a persistent search state.
- There is no background search or cataloging loop.
- The MCP surface is not progressive-discovery based.

## GitHub Webhook Route

Route: `webview/apps/webapp/src/app/api/webhooks/github/route.ts`.

Current behavior:

- Verifies `x-hub-signature-256` using `GITHUB_WEBHOOK_SECRET`.
- Parses installation, installation_repositories, push, repository, pull
  request, issues, and ping events.
- Logs or constructs local objects.
- Handler bodies have TODOs and do not persist installation data or enqueue
  ingestion jobs.

This route is a useful skeleton, but update-on-push is not wired.

## Docker and Environment

`docker-compose.yml` services:

- `db`: Postgres 16 Alpine.
- `api`: ingestion FastAPI image.
- `web`: Next/web image.

Shared mount:

- `./ingested_repos:/ingested_repos` is mounted into both API and web.

Declared volumes:

- `pg_data`
- `ingested_repos`

The named `ingested_repos` volume is declared, but the services use the bind
mount `./ingested_repos`.

Ingestion Dockerfile:

- Installs `@sourcegraph/scip-typescript`.
- Installs `@sourcegraph/scip-python`.

Important environment variables:

- `DATABASE_URL`
- `INGESTION_API_URL`
- `ANALYSIS_DB_DIR`
- `OPENAI_API_KEY`
- `GITHUB_TOKEN`
- `SUMMARIES_BASE_URL`
- `SUMMARIES_MODEL`
- `SUMMARIES_API_KEY`
- `MAX_REQUESTS_PER_SECOND`
- `EMBEDDINGS_BASE_URL`
- `EMBEDDINGS_MODEL`
- `EMBEDDINGS_API_KEY`
- `PDF_MAX_BYTES`
- `PDF_OCR_ENABLED`
- `DOC_EMBED_MAX_CHARS`

Dev script:

- `tools/dev.sh` can start DB, API, and web.
- API command: `uv run uvicorn api.main:app --app-dir src --reload`.
- Web command: `pnpm dev`.
- It symlinks root `.env.local` into webapp and ingestion when present.

Stale tool:

- `tools/uv_export_requirements.sh` appears to `cd` into `python`, but the repo
  has `ingestion`.

## Tests and Drift

Python tests exist under `ingestion/tests`.

Useful current-ish tests:

- Incremental parsing and changed-file behavior.
- Summary graph/subgraph behavior.
- Package registry and monorepo configuration tests.

Stale tests:

- API integration tests target endpoints not registered today:
  `/health`, `/files`, `/definitions`, `/imports`, `/function-calls`,
  `/type-references`, `/search/semantic/batch`.
- Parser tests import deleted or renamed models such as `FunctionCallModel`.
- Import/export tests expect populated imports/exports, but parser returns
  empty lists.

Frontend tests:

- No checked-in frontend tests were found.
- Shared package `test` script exits with failure.

## Current Strengths

The codebase has several strong foundations:

- Clear separation between app metadata and per-repo analysis state.
- Real parsing pipeline with Tree-sitter and SCIP.
- Dependency-aware summary ordering with SCC handling.
- Existing FTS and vector search.
- Existing doc upload and relevant-doc retrieval.
- Existing Next UI for file exploration, summaries, graphs, and chat.
- Existing MCP endpoint and shared agent search tool.
- Existing Docker/dev orchestration.

## Current Risks and Cleanup Backlog

Highest-priority correctness issues:

1. Make branch selection real or remove it from the API until implemented.
2. Fix delta propagation from `HybridParser` to ingestion worker.
3. Regenerate or fix OpenAPI TypeScript types.
4. Remove stale `db_path` request fields in tRPC.
5. Stop casting ingestion responses to include `status`.
6. Align Python SQLAlchemy analysis schema and TypeScript Drizzle read schema.
7. Fix JavaScript query capture mismatch.
8. Decide whether imports/exports are supported; either implement them or
   remove stale tables/tests/UI expectations.
9. Stop returning success for unknown job IDs.
10. Add durable jobs before webhooks or Drive sync.

Security and production issues:

1. Replace wildcard CORS with configured origins.
2. Add real auth and repo permission checks.
3. Replace global anonymous conversation reuse.
4. Scope MCP access by authenticated user, repo, branch, and granted scopes.
5. Store GitHub App installation records and use installation tokens instead
   of a global `GITHUB_TOKEN`.
6. Encrypt OAuth refresh tokens and sensitive installation metadata.
7. Add audit logs for ingestion, MCP calls, and agent actions.
8. Ensure worker-created clone mutations cannot affect source of truth.

Operational issues:

1. Add queue-backed workers.
2. Add job retries, cancellation, deduplication, and idempotency keys.
3. Add webhook delivery deduplication.
4. Add metrics and traces by job, repo, branch, commit, and user.
5. Add schema migrations for analysis DBs or centralize analysis storage.
6. Add cleanup and retention policies for clones, artifacts, and embeddings.

## Open Questions

These are not answered by the current code:

- Should each branch be a separate analysis DB, or should one DB hold multiple
  branch snapshots?
- Should per-repo SQLite remain the primary analysis store, or become an
  export/offline artifact?
- Should summaries be regenerated per commit, per branch head, or by content
  hash reuse across branches?
- Should docs uploaded by users be associated with repos, branches, workspaces,
  or users independently?
- How should Drive document permissions interact with repo permissions?
- How much write access should MCP expose?
- Should background agents only create findings, or also open PRs/issues?

