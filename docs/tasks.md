# Task Backlog

Created: 2026-06-04
Updated: 2026-06-05 — Part 1 (31 bugs) is complete and has been removed
from this document: 30 fixed, 1 not applicable (its target code lived in
the stashed docs-upload WIP). Every fix landed TDD-first (10 new
`test_bugfix_*.py` files, 46 tests), passed full verification against the
pre-fix baseline, and survived a three-lens adversarial review. See git
history for the diffs.

What remains below: the code changes — features, refactors, and cleanup,
ordered hardest to least hard. Sources: `docs/legacy-codebase.md`,
`docs/ideal-codebase.md`, `docs/platform-deep-dive.md`,
`docs/implementation-playbook.md`, and the 2026-06-04 code pass. Phases
refer to `docs/ideal-codebase.md`.

Difficulty accounts for both the fix and the verification cost:

- **XL** — architectural; multi-week; touches several subsystems.
- **L** — multi-day; needs design decisions or new tests.
- **M** — about a day; localized but subtle or needs fixture coverage.
- **S** — hours; mechanical once decided.
- **T** — trivial; minutes.

---

## Code Changes

### XL — architectural

1. **LSP-first indexing (Phase 4).** Replace tree-sitter+SCIP line-mapping
   as the semantic source of truth with an LSP broker: language-server
   catalog, sandboxed worker runtime, JSON-RPC client, normalization of
   symbols/references/hovers/diagnostics into `code_symbols`/`symbol_edges`
   with stable symbol keys (path+container+name+kind+signature hash, never
   line numbers), tree-sitter demoted to chunking/fallback. Hardest single
   item in the backlog: new infrastructure, per-language quirks, dependency
   installation policy. The tree-sitter+SCIP path was bug-fixed on
   2026-06-05 (JS captures, symbol-mapper name fallback, same-line dedup,
   tsconfig extends) but remains line-mapping based — LSP replaces it, so
   do not gold-plate that path further.

2. **Analysis storage migration: per-repo SQLite → Postgres + pgvector
   behind a permissioned API (Storage Strategy + principle 10; underpins
   Phase 1).** Move files/symbols/references/summaries/embeddings into
   central Postgres keyed by snapshot; kill direct `file://` libSQL reads
   from the webapp (the whole `turso-db` mirror-schema drift class
   disappears); SQLite remains dev/scratch/export. Touches ingestion writes,
   every tRPC analysis procedure, search, and deployment topology. Note the
   documented escalation path: Qdrant only if/when pgvector's filtered
   vector search becomes the bottleneck (`implementation-playbook.md`,
   "Index Choice").

3. **Code Mode MCP server (Phase 5).** Replace the single `codebase-qna`
   tool with `search()`/`execute()` running sandboxed JS against a typed SDK
   (repos/branches/search/files/symbols/graph/docs/findings namespaces);
   isolate runtime with no fs/env/network, CPU/memory/output caps, audit
   logs, scoped permissions. Depends on the read APIs from item 2 and auth
   from item 5.

4. **Background finding agents (Phase 6).** Refactor/security/schema-drift/
   test-drift/docs-freshness catalogers producing structured `findings`
   (evidence spans, confidence, fingerprint dedupe) with agent_runs and
   tool_calls tables, finding UI, and scheduling after ingest/push.

5. **Auth and permission model.** Sign-in, orgs/memberships, per-user
   repo grants, scoped conversations (replaces the global-anonymous
   fingerprint `"global"` design in `messagePersistence.ts`), MCP
   client authentication (today `withMcpAuth` blindly trusts the
   `x-repo-id` header — `api/mcp/route.ts`), audit events. Every
   later phase assumes this exists.

### L — multi-day

6. **Durable job queue.** Replace the in-memory `_jobs` dict
   (`job_manager.py`) with a jobs table + queue: states, retries,
   cancellation, dedupe keys, concurrency caps, survival across restarts.
   Prerequisite for webhooks, Drive sync, and background agents. Unknown
   job IDs now 404 honestly (fixed 2026-06-05) and the webview poller
   handles lost jobs, but only a durable store removes the
   jobs-lost-on-restart class entirely.

7. **Branch tracking + immutable snapshots (Phase 1).** `tracked_branches`,
   `source_snapshots` unique on `(repository_id, commit_sha)`, branch-aware
   clone/fetch, snapshot IDs on files/symbols/summaries/embeddings, branch
   selector UI. Builds on items 2 and 6. The ignored `branch` field was
   stripped from the ingest API on 2026-06-05; this item is what makes
   branches real.

8. **GitHub App + durable webhooks (Phase 2).** Installation records,
   installation tokens replacing the global `GITHUB_TOKEN`
   (`git_utils.py` `GitHubAppAuth` is token-based despite its name),
   webhook delivery persistence + dedupe, update-on-push enqueueing for
   tracked branches. The current receiver verifies HMAC then drops every
   event (`api/webhooks/github/route.ts`). Requires item 23
   (token encryption at rest) before storing any installation credentials.

9. **Hash-based regeneration DAG.** Multi-level hashes (raw / normalized /
   structure / semantic-input / dependency) driving summary+embedding
   invalidation with propagation that stops when output hashes don't change;
   dedupe queue keys. Delta propagation got its minimal fix on 2026-06-05
   (the worker now actually receives the parse delta); this item is the
   principled replacement for that plumbing.

10. **Google Drive connector (Phase 3).** OAuth, folder picker, changes
    cursor + watch renewal, export of Docs/Sheets/Slides/PDF, document
    revisions/chunks, summaries, embeddings, 3-5 display tags with source
    links. Requires item 23 for refresh-token storage. Note: a prototype of
    doc upload/relevance (local files, not Drive) exists in `stash@{0}` on
    branch `docs-ingestion`.

11. **Multi-turn agent search upgrade.** Add the missing read-exact-span
    tool (the prompt already asks for targeted spans no tool provides),
    symbol/graph expansion, a second-pass retrieval loop, persisted agent
    runs and tool calls; lift the 2-tool-call budget
    (`sendMCPMessage.ts`) once span reads keep cost bounded.

12. **Structured LLM outputs + model policy layer + cost tracking.**
    Replace `<gist>` string-splitting with schema-validated outputs (the
    parser was hardened against malformed tags on 2026-06-05, but the tag
    protocol itself remains fragile). Route all model calls through
    OpenRouter behind a `model_policies` layer — per-task model candidates,
    provider routing, and fallback policy (preferred → fallback →
    schema-capable → repair retry) — replacing the scattered
    `SUMMARIES_*`/`EMBEDDINGS_*` env-var selection. Record every call in
    `llm_requests` (tokens, cost, latency) aggregated by org/repo/job/
    feature. Real per-call token usage is now captured in-process
    (2026-06-05); this item persists and aggregates it.

13. **Schema source-of-truth unification.** One generator pipeline:
    FastAPI OpenAPI → TS types in CI (`api.ts` was regenerated once on
    2026-06-05 and the `db_path`/`status` drift fixed; CI generation is
    what prevents recurrence); analysis read schema derived from the Python
    models or retired entirely by item 2; delete the malformed
    introspection CHECK constraints in `turso-db/schema.ts` and the dead
    pgEnums (`packages/shared/src/db/migrations/schema.ts`); reconcile the
    hand-written `000_seed_schema.sql` with `schema.ts` and add a real
    migration runner (the initdb mount applies only on first boot —
    `docker-compose.yml`).

### M — about a day

14. **CI quality gates.** `.github/workflows/build-all.yml` only builds
    Docker images; add pytest, ruff, basedpyright, eslint, and `tsc
    --noEmit` jobs so CONTRIBUTING's pre-commit checklist is enforced; set
    up a webview test runner (today: zero TS tests). Note: the `uv sync`
    console-script shims are broken in this environment — CI should invoke
    via `uv run python -m pytest|ruff|basedpyright`.
15. **Fix or retire the remaining stale Python tests.** After the
    2026-06-05 cleanup (import/export suite deleted with the dead feature;
    three `<gist>` tests updated to the new contract), what remains broken
    is all pre-existing: collection errors in `test_function_calls.py`,
    `test_jsx_components.py` (import deleted `FunctionCallModel`/
    `ImportModel`), `test_type_extraction.py` (`TypeReferenceModel`),
    `test_monorepo_configurations.py` + `test_package_registry_enhanced.py`
    (moved `package_registry` module path); failures in
    `test_git_incremental_parsing.py` (monkeypatches a non-existent
    attribute; machine-specific fixture paths),
    `test_repository_integration.py`, and `test_parallel_ai_summaries.py`
    (old `generate_summaries_parallel` signature). Decide per suite: fix,
    rewrite, or delete.
16. **Invert the shared→webapp dependency.** `packages/shared/src/tools/
    semantic-search.ts` deep-imports `../../../../apps/webapp/...`
    (project-config, turso-db, types). Move those modules into the shared
    package or inject them; a "shared" package must not depend on an app.
17. **Logging migration.** Replace `print()` across the Python pipeline
    (`parser.py`, `scip_symbol_resolution.py`, `package_registry.py`,
    `path_utils.py` prints on every path resolution, `manager.py`,
    `netx.py`, `openai_client.py`) with the module logger / structured
    logging. (Files touched by the bug fixes already use the module
    logger in changed code; this item is the full sweep.)
18. **Stop re-creating engines per request.** Each `/search`/docs call
    constructs a `DatabaseManager`, re-runs `CREATE TABLE/FTS/vec` DDL and
    reloads the sqlite-vec extension (`manager.py`). Cache open handles per
    slug with an eviction policy. Same disease in tRPC: ~10 `analysis.ts`
    procedures repeat the open/close boilerplate — extract a helper or
    middleware.
19. **Clone containment.** `package_registry.py` mutates the cloned
    repo (writes root `tsconfig.json`, symlinks `node_modules`) as a side
    effect of constructing `PackageRegistry`. Make mutation opt-in and
    explicit, treat clones as disposable worker scratch, and never reuse a
    mutated clone for git diffs.
20. **`/health` endpoint + smoke tests (Phase 0).** Liveness/readiness for
    the API plus a smoke test covering `/ingest/github` → poll → `/search`.
21. **Decide the managed-workspace TODO.** pnpm/yarn workspace handling is
    disabled (`package_registry.py` "@TODO: managed workspaces have
    some issues with SCIP") and silently falls through; fix or document the
    degradation. (Moot if item 1 lands first.)
22. **Observability.** Structured metrics and traces keyed by
    job/repo/branch/commit/user across ingestion, search, chat, and MCP:
    queue depth, job latency/retries, model latency/cost, search latency by
    stage, webhook delivery failures. Wire trace IDs from webhook → job →
    summary/embedding/agent answer. Builds on items 6 and 12.
23. **Encrypt provider tokens at rest.** OAuth refresh/access tokens and
    GitHub App installation secrets must never live in plaintext columns —
    envelope encryption (KMS or libsodium sealed boxes) with key versioning.
    Prerequisite for items 8 and 10; today the only credential is the env
    `GITHUB_TOKEN`, so build this before the first token is stored.

### S — hours

24. **Dead-code sweep.** Empty `ingestion/src/llm_parsing/` (only
    `__pycache__` remains); `tools/uv_export_requirements.sh` (cd's into
    nonexistent `python/`, references Bazel) plus vestigial Bazel
    `.gitignore` entries; `MessageInput.tsx` (zero importers);
    `useActiveDefinition.tsx`, `parseXml.ts`, `lib/constants.ts` message
    limits (unused); commented-out PackagesView/FloatingOutlinePanel blocks
    in `NotebookView.tsx`; `_generate_placeholder_summary`
    and commented blocks in `summaries.py`;
    `_find_def_occurrence_and_container`
    (`scip_symbol_resolution.py`); `find_all_tsconfigs`
    (`package_registry.py`); stale `lib/prompts/MCPPrompt.md` if the
    inline prompt stays canonical; the fake `/api/ingestion/start` route
    returning hardcoded success; dead
    `turso_database_url`/`pinecone_*` fields on `JobResult`
    (`job_manager.py`); unused `supabaseDb` threading through
    `batchSearchTool.ts`/`sendMCPMessage.ts`; never-populated
    `is_exported`/`complexity_score` on `EmbeddingModel`
    (`models.py`). Consider adding `*.scip` to `.gitignore` (test runs can
    leak `index.scip` artifacts).
25. **Migrate `api/config.py` to pydantic-settings.** The validated config
    module added on 2026-06-05 is a stdlib dataclass with manual
    `os.getenv` parsing because pydantic-settings was not an installed
    dependency; `python.md` mandates pydantic-settings for env validation.
    Adding the dependency needs sign-off, then the migration is mechanical
    (the tests in `test_bugfix_api.py` pin the behavior).
26. **Validate the remaining webhook payloads with Zod.**
    `pull_request`/`issues` handlers index into payloads unvalidated, unlike
    the install/push/repo paths (`api/webhooks/github/route.ts`).
27. **Surface silent caps in responses.** FTS rows cast to `unknown` with
    `@todo` zod notes (`UserWorkspace.tsx`, `analysis.ts`).
28. **Fix the `inheritence` misspelling** in the
    `definition_dependencies` check constraint (`models.py`) — schema
    change, so batch it with the next analysis-schema migration (item 2 or
    13), not alone.
29. **Retention/GC policy.** Clone directories, generated artifacts, and
    orphaned embeddings accumulate forever; add TTL/sweep policies and
    on-delete cascade verification (today `/repo/delete` covers the happy
    path only).
30. **Defensive graph handling.** `parallel_summaries.py` reverses with
    `copy=False`, producing a live view over caller-owned graphs that are
    also consumed elsewhere (`definition_graph` feeds
    `build_file_dependency_graph`). Not currently corrupting (NetworkX
    returns a read-only view), but fragile — use `copy=True` or document
    the ownership.

### T — trivial

31. **README/docs corrections:** ingestion README still references Poetry
    (CONTRIBUTING already flags it; uv is current).
32. **`docker-compose.yml` tidy-up:** named volume `ingested_repos` is
    declared but the services use the bind mount; `NODE_ENV` set in two
    places (baked build env + runtime); investigate whether the
    `platform: linux/amd64` pin on `api` is still required (it forces
    emulation on Apple Silicon).

### Deferred platform workstreams

The deep-dive and playbook schedule a second horizon of work that this
backlog deliberately defers until the core (items 1-13) lands. Recorded
here so nothing is silently dropped:

- **Connector framework + integrations (XL).** Manifest/lifecycle contract
  and normalized event types, then Slack channel agent (scoped per-channel
  knowledge), Linear/GitHub-Issues work-item ingestion, Google Meet
  transcript ingestion, OneDrive/SharePoint via Microsoft Graph
  (`platform-deep-dive.md` "Integration Assembly Framework" and provider
  sections).
- **Temporal memory + verifier stack (XL).** Bitemporal entity versions,
  temporal embeddings/summaries, claim extraction, the 10-layer verifier
  pipeline, contradiction search (`platform-deep-dive.md` "Temporal Memory
  and Verification") — required for regulated-data tenants, not for the
  core product loop.
- **Rust migration of hot paths (XL).** Workers, LSP broker, graph/hash
  engine, search orchestration, MCP sandbox host
  (`implementation-playbook.md` "Best-Fit Programming Languages") — a
  language-split decision to revisit once the architecture stabilizes.
- **Blast-radius engine (L).** Diff → changed symbols → reverse dependents
  → tests/docs/services → risk score, surfaced in UI/PRs
  (`implementation-playbook.md` "Blast Radius of Code Changes").
- **GitHub PR review bot (L).** Checks API + deduped inline findings
  (`implementation-playbook.md` "Code Review Bot Integration").
- **Go-to-definition UI + evidence drawer, reference chips, tag ranking
  (L).** First-class navigation from summaries/citations/graph to exact
  spans; summary cards with ranked tag chips and reference chips
  (`implementation-playbook.md`, `platform-deep-dive.md` "Cleaner Views").
- **Documentation profiles + summary-correction feedback (M).** Per-repo
  doc style profiles; "this summary is wrong" feedback stored, classified,
  and folded back into regeneration.
- **Agent harness generator (M).** Generate README/DESIGN/AGENTS/CLAUDE
  docs from indexed facts with citations.
- **Task clustering + skill mining (M).** Log developer questions across
  MCP/Slack/chat, dedupe lexically+semantically, promote recurring clusters
  to skills/playbooks.
- **Intra-/inter-repo service graphs (M).** Detect services via
  compose/k8s/manifests/env wiring; cross-repo edges via packages, schemas,
  and tickets.

---

## Suggested sequencing (difficulty is not order)

The list above ranks by difficulty as requested; do not execute it
top-down. With the bug backlog cleared (2026-06-05), the cheap de-risking
moves are the Phase-0 items: CI gates (14), stale-test retirement (15),
and `/health` + smoke tests (20). Then: durable jobs (6) → storage
migration + snapshots (2, 7) → GitHub App/webhooks (8, with 23 first) →
hash regeneration (9) → LSP (1) → Code Mode MCP (3) → Drive (10) →
background agents (4). Auth (5) can start in parallel any time. Do not
invest further in the tree-sitter+SCIP semantic path (items 19, 21 are
maintenance-only) — LSP (1) replaces it.
