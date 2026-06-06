# Ideal Codebase Documentation

Research date: 2026-06-02

This document describes the target architecture for turning the current
AutoDocs prototype into a signed-in, branch-aware, GitHub-and-Google-Drive
connected code intelligence platform with LSP-backed indexing, document
embeddings, Code Mode-style MCP, multi-turn agent search, and asynchronous
background cataloging.

The current-state companion document is `docs/legacy-codebase.md`.

## Design Goal

Build a system where a user can:

1. Sign in.
2. Connect GitHub.
3. Select repositories and branches.
4. Keep selected branches updated on every push.
5. Switch branches in the UI and in agent queries.
6. Connect Google Drive.
7. Grant access to a Drive folder.
8. Embed all documents in that folder.
9. See 3-5 useful tags on relevant documents.
10. Click tags/results through to the original Google Doc, Sheet, Slide, PDF,
    or file.
11. Ask agents questions across code and documents.
12. Let agents run multiple parallel searches and multi-turn retrieval.
13. Let background agents asynchronously catalog refactor, cleanup, security,
    test, documentation, and architecture opportunities.
14. Expose repository intelligence through a lightweight MCP server following
    the fixed-token Code Mode pattern: a small tool surface with progressive
    discovery.

## External Source Context

Primary sources consulted for the target design:

- GitHub webhook docs:
  https://docs.github.com/webhooks/about-webhooks-for-repositories
- GitHub webhook event payload docs:
  https://docs.github.com/webhooks/event-payloads
- GitHub Apps and installation token docs:
  https://docs.github.com/en/rest/apps/apps
- GitHub App vs OAuth App docs:
  https://docs.github.com/en/enterprise-cloud@latest/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps
- Google Drive API changes docs:
  https://developers.google.com/workspace/drive/api/guides/manage-changes
- Google Drive export formats:
  https://developers.google.com/drive/api/guides/ref-export-formats
- Language Server Protocol 3.17 specification:
  https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
- Model Context Protocol specification:
  https://modelcontextprotocol.io/specification/2025-06-18/basic/index
- pgvector:
  https://github.com/pgvector/pgvector

Secondary source used for MCP architecture comparison:

- Cloudflare Code Mode MCP blog:
  https://blog.cloudflare.com/code-mode-mcp

The Cloudflare source is useful because it articulates a practical MCP pattern:
instead of exposing hundreds or thousands of tools, expose a tiny stable
surface, typically `search()` and `execute()`, and let the model write code
against a typed SDK in a sandbox. The blog is not a formal MCP specification,
but it is directly relevant to the product direction.

## Core Principles

1. User and permission boundaries come first.
   Every repo, branch, Drive folder, document, embedding, finding, chat, and
   MCP call must be scoped to a user or organization and its grants.

2. Branches are first-class.
   A branch is not a string passed through a request. It is a tracked source of
   snapshots, jobs, summaries, embeddings, and findings.

3. Snapshots are immutable.
   A commit analysis should be reproducible. Mutable branch heads point to
   immutable snapshots.

4. Reuse by content hash.
   Summaries, embeddings, and findings should be reused across branches when
   file or symbol content is identical.

5. LSP is the semantic source of truth where available.
   Tree-sitter remains useful for fast structure and chunking, but LSP should
   drive definitions, references, diagnostics, hovers, implementations, type
   definitions, and workspace symbols.

6. Documents are first-class knowledge sources.
   Drive docs are not fake code files. They need their own connector metadata,
   chunks, embeddings, tags, links, revisions, and permissions.

7. MCP should be compact and discoverable.
   Agents should not receive a large static tool list. They should receive a
   small API surface and discover capabilities/data progressively.

8. Background agents create reviewable artifacts.
   They should not silently rewrite a codebase. They should create findings,
   suggested patches, issues, PRs, or queued tasks with evidence and confidence.

9. Operational state is durable.
   Jobs, webhook deliveries, Drive cursors, branch snapshots, agent runs, and
   tool calls must survive restarts.

10. UI reads from an API, not local analysis DB files.
    Direct file access is useful locally, but a product needs permission checks,
    branch scoping, pagination, and stable contracts.

## Target Architecture

```text
Browser / MCP client / IDE client
  |
  v
Web/API Gateway
  |-- Auth/session
  |-- tRPC/REST/GraphQL app APIs
  |-- MCP Code Mode server
  |-- Webhook receivers
  |
  v
Core App Database (Postgres + pgvector)
  |-- users/orgs/auth grants
  |-- GitHub installations/repos/branches/snapshots
  |-- Drive folders/files/revisions/chunks/tags
  |-- code files/symbols/references/summaries/embeddings
  |-- jobs/runs/findings/conversations/tool calls/audit
  |
  +--> Object Storage
  |      |-- raw repo archives or file blobs
  |      |-- exported Drive document text
  |      |-- index artifacts
  |      |-- logs and trace payloads
  |
  +--> Durable Queue
         |-- GitHub sync jobs
         |-- Drive sync jobs
         |-- LSP indexing jobs
         |-- summary jobs
         |-- embedding jobs
         |-- background agent jobs

Workers
  |-- GitHub connector worker
  |-- Drive connector worker
  |-- LSP broker/index worker
  |-- summary and embedding worker
  |-- background agent worker
```

Services:

- Web app: UI, auth flows, branch selector, docs selector, chat, findings.
- API gateway: validates user/session, scopes requests, exposes stable APIs.
- Connector service: GitHub App and Google Drive OAuth integration.
- Queue service: durable jobs, retries, deduplication, cancellation.
- Source snapshot service: immutable source state per repo/branch/commit.
- LSP broker: starts language servers, manages workspaces, extracts semantic
  facts.
- Knowledge store: central DB plus vector index.
- Summary service: generates code and document summaries.
- Embedding service: embeds code and document chunks.
- Agent service: foreground Q&A and background cataloging.
- MCP service: compact Code Mode interface.
- Object storage: large blobs and generated artifacts.

## Storage Strategy: Postgres vs SQLite

### Recommended Primary Store

Use Postgres as the primary product database. Add pgvector for embeddings or
use a dedicated vector service if scale demands it.

Why:

- User auth and permissions are relational.
- GitHub installations, Drive grants, branches, snapshots, and jobs need
  durable relationships.
- Background findings need status, assignment, history, and evidence.
- Webhook and Drive change processing need idempotency and cursors.
- Branch-aware querying benefits from SQL joins and indexes.
- pgvector keeps metadata filters and vector search in one transactional system
  for the first serious product version.

### Where SQLite Still Fits

Keep SQLite as:

- A local development mode.
- A worker scratch DB for fast isolated indexing.
- An export format for "download this repo's intelligence".
- A cache for branch snapshot data.
- A fallback for offline or self-hosted single-user setups.

SQLite should not remain the primary production source of truth if the product
needs multi-user auth, GitHub webhooks, Drive permissions, branch switching,
background agents, and MCP access control.

### Migration Direction

Move from:

```text
public_projects in Postgres
repo_slug.db in local SQLite
```

to:

```text
Postgres:
  github_repositories
  tracked_branches
  source_snapshots
  source_files
  code_symbols
  symbol_references
  documents
  document_chunks
  embeddings
  findings

Optional artifacts:
  per-snapshot SQLite export/cache
```

## Target Data Model

This is a logical schema, not a final migration.

### Identity and Access

`users`

- `id`
- `email`
- `name`
- `image_url`
- `created_at`
- `updated_at`

`organizations`

- `id`
- `name`
- `slug`
- `created_at`

`memberships`

- `org_id`
- `user_id`
- `role`

`oauth_accounts`

- `id`
- `user_id`
- `provider` (`github`, `google`)
- `provider_account_id`
- `scope`
- `access_token_ciphertext`
- `refresh_token_ciphertext`
- `expires_at`
- `created_at`
- `updated_at`

`audit_events`

- `id`
- `actor_user_id`
- `org_id`
- `event_type`
- `target_type`
- `target_id`
- `metadata_json`
- `created_at`

### GitHub

`github_installations`

- `id`
- `org_id`
- `installation_id`
- `account_login`
- `account_type`
- `permissions_json`
- `repository_selection`
- `suspended_at`
- `created_at`
- `updated_at`

`github_repositories`

- `id`
- `org_id`
- `installation_id`
- `github_repo_id`
- `owner`
- `name`
- `full_name`
- `private`
- `default_branch`
- `html_url`
- `clone_url`
- `archived`
- `disabled`
- `created_at`
- `updated_at`

`tracked_branches`

- `id`
- `repository_id`
- `branch_name`
- `enabled`
- `current_head_sha`
- `last_indexed_sha`
- `last_successful_snapshot_id`
- `created_at`
- `updated_at`
- unique `(repository_id, branch_name)`

`source_snapshots`

- `id`
- `repository_id`
- `branch_id`
- `commit_sha`
- `parent_sha`
- `tree_sha`
- `status`
- `created_from` (`manual`, `webhook`, `scheduled`)
- `indexed_at`
- unique `(repository_id, commit_sha)`

`webhook_deliveries`

- `id`
- `provider` (`github`)
- `delivery_id`
- `event_type`
- `installation_id`
- `repository_id`
- `payload_hash`
- `received_at`
- `processed_at`
- `status`
- unique `(provider, delivery_id)`

### Source Files and Symbols

`source_files`

- `id`
- `snapshot_id`
- `path`
- `language`
- `content_hash`
- `blob_sha`
- `size_bytes`
- `is_deleted`
- `object_storage_key`
- unique `(snapshot_id, path)`

`code_symbols`

- `id`
- `snapshot_id`
- `file_id`
- `stable_symbol_key`
- `lsp_symbol_name`
- `display_name`
- `kind`
- `range_start_line`
- `range_start_col`
- `range_end_line`
- `range_end_col`
- `selection_start_line`
- `selection_start_col`
- `selection_end_line`
- `selection_end_col`
- `container_name`
- `signature`
- `documentation`
- `content_hash`
- unique `(snapshot_id, stable_symbol_key)`

`symbol_references`

- `id`
- `snapshot_id`
- `source_file_id`
- `source_symbol_id`
- `target_symbol_id`
- `target_uri`
- `reference_kind`
- `range_start_line`
- `range_start_col`
- `range_end_line`
- `range_end_col`

`diagnostics`

- `id`
- `snapshot_id`
- `file_id`
- `source`
- `severity`
- `code`
- `message`
- `range_start_line`
- `range_start_col`
- `range_end_line`
- `range_end_col`

`code_chunks`

- `id`
- `snapshot_id`
- `file_id`
- `symbol_id`
- `chunk_type` (`file`, `symbol`, `span`)
- `content_hash`
- `text`
- `token_count`
- `metadata_json`

### Summaries and Embeddings

`summaries`

- `id`
- `snapshot_id`
- `entity_type` (`file`, `symbol`, `doc`, `doc_chunk`, `finding`)
- `entity_id`
- `summary_kind` (`short`, `full`, `technical`, `tag_basis`)
- `model`
- `input_hash`
- `summary_text`
- `created_at`
- unique `(entity_type, entity_id, summary_kind, input_hash)`

`embeddings`

- `id`
- `org_id`
- `snapshot_id`
- `entity_type`
- `entity_id`
- `content_hash`
- `embedding_model`
- `embedding_dims`
- `embedding vector(1536)` or external vector ID
- `metadata_json`
- `created_at`
- unique `(entity_type, entity_id, embedding_model, content_hash)`

If using pgvector, add indexes such as:

- HNSW or IVFFlat on `embedding`.
- B-tree indexes on `org_id`, `snapshot_id`, `entity_type`, and metadata
  filter columns.

### Google Drive

`drive_connections`

- `id`
- `user_id`
- `org_id`
- `google_account_email`
- `scope`
- `access_token_ciphertext`
- `refresh_token_ciphertext`
- `expires_at`
- `created_at`
- `updated_at`

`drive_folders`

- `id`
- `connection_id`
- `drive_folder_id`
- `name`
- `web_view_link`
- `enabled`
- `start_page_token`
- `last_change_token`
- `watch_channel_id`
- `watch_resource_id`
- `watch_expires_at`
- `created_at`
- `updated_at`

`drive_files`

- `id`
- `folder_id`
- `drive_file_id`
- `name`
- `mime_type`
- `web_view_link`
- `icon_link`
- `parents_json`
- `modified_time`
- `version`
- `md5_checksum`
- `export_mime_type`
- `permission_fingerprint`
- `last_indexed_revision`
- `status`
- unique `(folder_id, drive_file_id)`

`document_revisions`

- `id`
- `drive_file_id`
- `revision_key`
- `content_hash`
- `exported_text_object_key`
- `exported_at`

`document_chunks`

- `id`
- `drive_file_id`
- `revision_id`
- `chunk_index`
- `heading_path`
- `text`
- `content_hash`
- `token_count`

`document_tags`

- `id`
- `drive_file_id`
- `revision_id`
- `tag`
- `confidence`
- `source` (`llm`, `rule`, `user`)
- `created_at`
- unique `(drive_file_id, revision_id, tag)`

Tags should be generated from summaries/chunks, not from filenames alone.
Limit display to 3-5 tags, but store more candidates if useful.

### Jobs and Agents

`jobs`

- `id`
- `org_id`
- `job_type`
- `status`
- `priority`
- `dedupe_key`
- `payload_json`
- `attempt_count`
- `max_attempts`
- `scheduled_at`
- `started_at`
- `finished_at`
- `error`
- `created_at`

`agent_runs`

- `id`
- `org_id`
- `user_id`
- `agent_type`
- `status`
- `scope_json`
- `input_json`
- `result_json`
- `started_at`
- `finished_at`

`tool_calls`

- `id`
- `agent_run_id`
- `tool_name`
- `input_json`
- `output_summary`
- `status`
- `duration_ms`
- `created_at`

`findings`

- `id`
- `org_id`
- `repository_id`
- `branch_id`
- `snapshot_id`
- `finding_type`
- `severity`
- `confidence`
- `title`
- `description`
- `evidence_json`
- `affected_spans_json`
- `recommended_action`
- `fingerprint`
- `status` (`open`, `accepted`, `dismissed`, `fixed`)
- `created_by_agent_run_id`
- `created_at`
- `updated_at`
- unique `(snapshot_id, fingerprint)`

## GitHub Sign-in and Repository Sync

### Auth Model

Use both:

- GitHub OAuth for user identity when the user signs in with GitHub.
- GitHub App installation for repository access and webhooks.

Do not rely on a single global `GITHUB_TOKEN` for product repository access.

Why GitHub App:

- Installation tokens are scoped to selected repositories and permissions.
- Webhooks are tied to installations.
- Repository access can be revoked or narrowed.
- Fine-grained permissions are clearer than broad OAuth scopes.

### Required GitHub App Permissions

Start minimal:

- Repository contents: read.
- Metadata: read.
- Pull requests/issues: read only if findings need PR/issue context.
- Checks or statuses: optional for CI-aware agents.

Events:

- `installation`
- `installation_repositories`
- `push`
- `repository`
- Optional: `pull_request`, `check_suite`, `check_run`, `issues`.

### Add Repository Workflow

```text
User signs in
  -> user installs GitHub App or selects an existing installation
  -> app lists installation repositories
  -> user selects repository
  -> app lists branches
  -> user selects branches to track
  -> create github_repository rows
  -> create tracked_branch rows
  -> enqueue initial sync for each selected branch
```

### Push Update Workflow

```text
GitHub push webhook
  -> verify signature
  -> store webhook_deliveries row
  -> dedupe by delivery ID
  -> parse branch from ref
  -> check whether branch is tracked
  -> update tracked_branches.current_head_sha
  -> enqueue github_sync job with repository, branch, before, after

github_sync worker
  -> get installation access token
  -> fetch/clone repository
  -> create source_snapshot for after commit
  -> diff against last successful snapshot
  -> enqueue LSP/index job
```

Idempotency:

- Webhook delivery ID prevents duplicate processing.
- `(repository_id, commit_sha)` prevents duplicate snapshots.
- Job `dedupe_key` prevents repeated indexing for the same branch head.

### Branch Switching

Branch switching should not mean recloning synchronously in the UI.

UI behavior:

- Branch selector lists tracked branches and indexing state.
- If the branch has an indexed snapshot, switch immediately.
- If the branch is tracked but stale, show current indexed commit and current
  head separately.
- If the branch is not tracked, let the user add it and enqueue initial sync.

API queries should include:

- `repository_id`
- `branch_id` or `branch_name`
- optional `snapshot_id`

The default should be the branch's last successful snapshot, not necessarily
the latest pushed commit.

## Google Drive Folder Sync

### OAuth Model

Use Google OAuth with Drive scopes chosen carefully.

Recommended initial scope:

- Prefer file/folder-scoped access where the picker can grant selected file
  access when possible.
- If full folder sync requires broader Drive access, clearly show what the user
  is granting and store only necessary metadata/content.

### Folder Connect Workflow

```text
User connects Google account
  -> user selects a Drive folder
  -> store drive_connection
  -> store drive_folder
  -> get start page token / change cursor
  -> enqueue initial folder crawl
```

### Initial Crawl

```text
drive_sync worker
  -> list files under selected folder recursively if enabled
  -> filter supported mime types
  -> export Google-native files to text/markdown-like content
  -> download text/PDF files as needed
  -> create drive_file rows
  -> create document_revision rows
  -> chunk documents
  -> summarize chunks/document
  -> embed chunks/document
  -> generate tags
```

Supported sources:

- Google Docs: export to plain text or markdown-like format.
- Google Sheets: export to CSV, TSV, or text summaries per sheet.
- Google Slides: export text speaker/content where available.
- PDFs: text extraction with OCR fallback.
- Markdown, text, HTML, CSV.

### Drive Changes

Use Drive change tokens and/or watch channels:

- Store `start_page_token`.
- Process changed files.
- Renew watches before expiration.
- Treat watches as invalidation triggers; use changes API as the durable cursor.

### Document Chunking

Chunk by structure first:

- Document title.
- Headings.
- Sheet names.
- Slide numbers.
- Table/section boundaries.

Then enforce token limits.

Each chunk should retain:

- Drive file ID.
- Revision ID.
- Chunk index.
- Heading path.
- Web link.
- MIME type.
- Source object type.

### Tags

Generate candidate tags from:

- Document title.
- Section headings.
- Summary.
- Top entities mentioned.
- Repo/code relevance when queried against a code context.

Display 3-5 tags. Store confidence and source.

Click behavior:

- Tag click can filter or navigate to a document result.
- Document click opens `web_view_link` for Google-native docs or Drive-hosted
  files.
- For Sheets, include sheet name in metadata when possible.

## LSP-first Code Intelligence

### Why Move from Tree-sitter + Mapper + SCIP to LSP

Current approach:

- Tree-sitter extracts syntax definitions.
- SCIP provides symbol occurrences.
- A line-based mapper links them.

Problems:

- Language support is limited.
- Mapping can fail for multiple symbols on the same line.
- Import/export support is incomplete.
- SCIP support depends on language-specific indexers.
- Some inferred languages raise unsupported errors.

LSP approach:

- Use each language's own language server for semantic facts.
- Query symbols, definitions, references, diagnostics, hovers, and types using a
  common JSON-RPC protocol.
- Keep Tree-sitter as a fallback and chunking parser.

### LSP Capabilities to Use

Minimum useful methods:

- `initialize`
- `textDocument/didOpen`
- `textDocument/documentSymbol`
- `workspace/symbol`
- `textDocument/definition`
- `textDocument/references`
- `textDocument/implementation`
- `textDocument/typeDefinition`
- `textDocument/hover`
- `textDocument/diagnostic` or publish diagnostics
- `workspace/semanticTokens` if useful

Optional:

- `textDocument/codeAction`
- `textDocument/rename`
- `textDocument/formatting`
- `workspace/executeCommand`

For indexing, prefer read-only semantic methods first. Mutating methods should
be separate and gated.

### Language Server Catalog

Initial catalog:

- TypeScript/JavaScript: `typescript-language-server` plus `tsserver`.
- Python: `pyright-langserver` or `basedpyright`.
- Go: `gopls`.
- Rust: `rust-analyzer`.
- Java: Eclipse JDT LS.
- C/C++: `clangd`.
- C#: OmniSharp or C# Dev Kit compatible server.
- Ruby: Solargraph or Ruby LSP.
- PHP: Intelephense or PHPActor.
- Swift: SourceKit-LSP.
- Kotlin: Kotlin language server.
- Dart: Dart analysis server.

The catalog needs:

- install command or container image
- startup command
- required project files
- supported extensions
- capability quirks
- indexing readiness signal
- timeout and memory defaults

### LSP Broker

The LSP broker should:

- Run language servers in sandboxed worker environments.
- Mount or materialize the repo snapshot.
- Start one server per language/workspace where needed.
- Track server lifecycle and readiness.
- Normalize LSP URIs to repository paths.
- Convert LSP ranges to stable source spans.
- Retry or degrade to Tree-sitter on language server failure.
- Store raw capability metadata for debugging.

### LSP Indexing Workflow

```text
lsp_index job
  -> materialize snapshot checkout
  -> detect languages and package managers
  -> install/restore dependencies only when needed and allowed
  -> start language servers
  -> discover files
  -> for each file:
       documentSymbol
       diagnostics
       hover for selected symbols
       references/definition/typeDefinition where supported
  -> normalize symbols and references
  -> persist source_files, code_symbols, symbol_references, diagnostics
  -> enqueue summary and embedding jobs
```

Dependency installation policy:

- Prefer lockfile-respecting installs.
- Avoid arbitrary lifecycle scripts unless explicitly allowed.
- Use network-restricted mirrors or cached package stores where possible.
- Record dependency install logs and hashes.

### Stable Symbol Keys

Use a stable key that can survive minor line shifts:

```text
repository_id
language
file_path
container_name
symbol_name
symbol_kind
signature_or_selection_text_hash
```

For languages with robust LSP or compiler symbol IDs, store those too, but do
not assume they are portable across servers.

### Tree-sitter After LSP

Tree-sitter should remain in the system for:

- fast file chunking
- syntax fallback
- rough symbol extraction when LSP fails
- detecting code blocks in docs
- language-independent structure

Tree-sitter should not be the only semantic source for references when a
language server is available.

### SCIP After LSP

SCIP can remain useful as:

- an optional indexing path for supported ecosystems
- an export format
- a fallback for repos where SCIP works better than a language server

But the target should not depend on line-based Tree-sitter-to-SCIP mapping as
the central semantic bridge.

## Summary Generation in the Ideal System

Use multiple summary levels:

- Symbol summary: purpose, behavior, inputs/outputs, side effects, dependencies.
- File summary: purpose, important symbols, local architecture, dependencies.
- Package/module summary: public surface, internal organization, integration
  points.
- Branch snapshot summary: what changed in this commit/sync.
- Document chunk summary: local content and entities.
- Document summary: full-document purpose, decisions, owners, dates, links.
- Cross-source summary: relation between docs and code areas.

Use dependency-aware ordering:

- Summarize leaves before dependents.
- Collapse cycles into SCC groups.
- Reuse summaries by content hash.
- Regenerate ancestors only when downstream summaries change meaningfully.

Prompts should be language-aware:

- Do not hardcode TypeScript in prompts.
- Include language, framework, package, and source span.
- Require structured output with a schema, not fragile tag splitting.

Store:

- model
- prompt version
- input hash
- output schema version
- citations
- token usage
- generated_at

## Embeddings in the Ideal System

Embed:

- code symbols
- files
- package summaries
- document chunks
- document summaries
- tags
- findings
- conversations when useful

Embedding metadata must include:

- org/user scope
- repository
- branch
- snapshot
- file path
- symbol ID
- Drive file ID
- revision ID
- document URL
- entity type
- language or MIME type
- content hash
- model and dimensions

Search should support:

- vector search
- BM25/FTS search
- symbol search
- path search
- diagnostic/finding search
- graph expansion
- hybrid ranking with reranking
- metadata filters
- branch/snapshot filters
- permission filters

## Code Mode MCP Server

### Target Tool Surface

Expose two primary tools:

```json
[
  {
    "name": "search",
    "description": "Search and inspect the typed AutoDocs capability/index schema. Returns compact matching capabilities, entities, and examples.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "description": "JavaScript async arrow function executed against a read-only discovery SDK"
        }
      },
      "required": ["code"]
    }
  },
  {
    "name": "execute",
    "description": "Execute sandboxed JavaScript against the authorized AutoDocs SDK for code, docs, search, graph, and findings operations.",
    "inputSchema": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "description": "JavaScript async arrow function executed against the authorized SDK"
        }
      },
      "required": ["code"]
    }
  }
]
```

`search()` is for capability and schema discovery. `execute()` is for composed
queries and authorized actions.

### SDK Shape

The sandboxed SDK should expose typed namespaces:

```ts
sdk.repos.list()
sdk.repos.get({ repo })
sdk.branches.list({ repo })
sdk.snapshots.latest({ repo, branch })

sdk.search.semantic({ query, scope, limit })
sdk.search.hybrid({ query, scope, limit })
sdk.search.symbols({ query, scope, limit })
sdk.search.paths({ query, scope, limit })
sdk.search.docs({ query, scope, limit })
sdk.search.findings({ query, scope, limit })

sdk.files.read({ fileId, startLine, endLine })
sdk.files.summary({ fileId })
sdk.symbols.get({ symbolId })
sdk.symbols.references({ symbolId, direction })
sdk.symbols.definition({ fileId, line, character })

sdk.graph.neighborhood({ entityType, entityId, depth })
sdk.docs.get({ documentId })
sdk.docs.openLink({ documentId })
sdk.docs.tags({ documentId })
sdk.findings.list({ scope, status, severity })
sdk.findings.get({ findingId })
```

For mutations, start with limited operations:

```ts
sdk.jobs.enqueueRepoSync({ repo, branch })
sdk.jobs.enqueueDriveSync({ folderId })
sdk.findings.updateStatus({ findingId, status })
```

Mutations should require explicit granted scope and should be audited.

### Sandbox Requirements

The code runner must:

- Run with no filesystem access.
- Run with no environment variable access.
- Disable arbitrary outbound fetch by default.
- Provide only the SDK object and safe standard APIs.
- Enforce CPU, wall-clock, memory, and output limits.
- Cap result sizes.
- Redact secrets.
- Log code, inputs, result summaries, duration, and actor.
- Scope all SDK calls by user/org/repo/branch permissions.
- Make write operations opt-in and separately permissioned.

If using a Worker isolate, mirror the Cloudflare-style approach. If running on
the server, use an equivalent sandbox such as an isolated V8 runtime with a
strict host API.

### Example MCP Discovery

An agent can ask what search capabilities exist:

```js
async ({ sdk }) => {
  return sdk.capabilities.search({ query: "references documents findings" });
}
```

It can then run a composed read:

```js
async ({ sdk }) => {
  const code = await sdk.search.hybrid({
    query: "GitHub webhook branch sync",
    scope: { repo: "autodocs", branch: "main" },
    limit: 8
  });

  const docs = await sdk.search.docs({
    query: "GitHub webhook branch sync",
    scope: { repo: "autodocs" },
    limit: 5
  });

  return { code, docs };
}
```

### Why This Is Better Than Many Tools

It gives the agent:

- Fixed context footprint.
- Progressive discovery.
- Parallel and multi-step composition inside one execution.
- Typed access to many operations without loading every operation as a tool.
- Server-side permission enforcement.
- Smaller final results returned to model context.

## Foreground Agent Search

The current `batch_search_codebase` tool is a good seed. The target system
should generalize it.

Search loop stages:

1. Parse user question into candidate scopes, entities, branches, files,
   symbols, document topics, and constraints.
2. Run parallel first-pass searches:
   - semantic code search
   - symbol search
   - path search
   - docs search
   - findings search
3. Inspect top results:
   - read exact file spans
   - inspect symbol references
   - expand graph neighborhood
   - fetch relevant doc chunks
4. Run a second-pass query if evidence is insufficient.
5. Rerank and dedupe.
6. Answer with citations and confidence.

The agent should support multiple turns:

- Store retrieved evidence in `agent_runs`.
- Store tool calls.
- Preserve branch/snapshot scope.
- Let follow-up questions reuse prior evidence but refresh if branch changed.

## Background Agents

Background agents should run asynchronously and create structured findings.

### Agent Types

Refactor cataloger:

- Finds duplicated logic.
- Finds oversized files/functions.
- Finds modules with unstable boundaries.
- Suggests consolidation.

Security cataloger:

- Looks for auth bypasses, wildcard CORS, token leakage, unsafe filesystem
  operations, webhook validation gaps, SSRF risks, and dependency risks.

Schema drift cataloger:

- Compares Pydantic schemas, generated OpenAPI types, SQLAlchemy models,
  Drizzle schemas, and migrations.

Test drift cataloger:

- Finds tests targeting deleted endpoints/models.
- Finds untested active routes.
- Finds frontend surfaces with no tests.

Docs freshness cataloger:

- Compares code changes to docs and summaries.
- Flags stale or contradictory comments.

Dependency graph cataloger:

- Finds high centrality modules, cycles, unstable dependency patterns, and
  likely extraction boundaries.

### Finding Format

Each finding should include:

- type
- severity
- confidence
- title
- evidence spans
- affected branch/snapshot
- affected files/symbols
- why it matters
- recommended action
- optional patch sketch
- fingerprint for dedupe

Agents should not auto-apply broad refactors by default. They should create
reviewable findings first.

### Scheduling

Trigger background agents:

- after initial repo ingestion
- after push sync
- after Drive folder sync
- on manual user request
- on schedule for tracked repos

Avoid rerunning everything:

- Use content hashes.
- Use finding fingerprints.
- Reuse summaries.
- Queue only changed scopes and ancestors/dependents.

## Product UI Target

### Workspace

Should show:

- connected GitHub installations
- repositories
- tracked branches
- branch indexing state
- current and last indexed commit
- Drive folders
- sync status
- latest findings
- latest background agent runs

### Repository View

Should include:

- branch selector
- snapshot/commit selector
- files tree
- symbol search
- docs tab
- source view
- dependency graphs
- findings tab
- chat drawer scoped to repo/branch/snapshot

### Documents View

Should include:

- Drive folder selector
- document list
- document type icon
- 3-5 tags
- relevance to selected file/symbol
- summary
- source link to Google Drive
- revision/index status

### Findings View

Should include:

- severity filters
- type filters
- branch/snapshot filters
- evidence spans
- accept/dismiss/fixed states
- optional "create issue" or "open PR" actions

### Chat

Chat must be scoped:

- user
- org
- repo
- branch
- snapshot
- optionally Drive folder

No global anonymous conversation should remain in the signed-in product.

## API Target

Stable backend API groups:

- `auth`
- `github`
- `drive`
- `repositories`
- `branches`
- `snapshots`
- `files`
- `symbols`
- `documents`
- `search`
- `findings`
- `jobs`
- `chat`
- `mcp`

Example endpoints:

- `GET /api/github/installations`
- `GET /api/github/installations/{id}/repositories`
- `POST /api/repositories/{id}/tracked-branches`
- `GET /api/repositories/{id}/branches`
- `POST /api/repositories/{id}/branches/{branch}/sync`
- `GET /api/repositories/{id}/branches/{branch}/snapshot`
- `GET /api/files/{file_id}`
- `GET /api/files/{file_id}/symbols`
- `GET /api/symbols/{symbol_id}/references`
- `POST /api/search`
- `GET /api/drive/folders`
- `POST /api/drive/folders`
- `GET /api/documents`
- `GET /api/documents/{id}`
- `GET /api/findings`
- `PATCH /api/findings/{id}`
- `GET /api/jobs/{id}`

Every endpoint should enforce access control centrally.

## Cleanup Needed in the Current Codebase

Before building the ideal system, stabilize the current base:

1. Fix API type generation.
   Regenerate `webview/apps/webapp/src/types/api.ts` from FastAPI OpenAPI.

2. Fix ingestion request/response drift.
   Remove stale `db_path` from tRPC payloads and stop expecting `status` in the
   enqueue response.

3. Make branches real.
   Add branch to `ensure_shallow_main`, clone/fetch logic, repository schema,
   job payload, and DB naming or snapshot model.

4. Fix delta propagation.
   Return delta from `HybridParser` or expose its `ASTParser.current_delta`
   directly.

5. Fix JS/JSX Tree-sitter captures.
   Either make JavaScript queries typed or make parser consume generic
   captures.

6. Decide imports/exports.
   Implement them or remove stale tests/tables/UI references.

7. Align schemas.
   Generate TypeScript read schema from Python models or move analysis reads
   behind an API.

8. Replace in-memory jobs.
   Add durable queue and job table.

9. Harden auth/CORS/MCP.
   Remove wildcard CORS and global anonymous chat behavior.

10. Convert GitHub webhook route from TODO skeleton to durable receiver.
    Verify, persist, dedupe, branch-filter, enqueue.

11. Move web analysis reads through a permissioned API.
    Direct `file://` DB access should be dev-only.

12. Remove stale comments.
    Turso/Pinecone/embedded-replica comments should match current behavior or
    be deleted.

## Migration Plan

### Phase 0: Stabilize Current Prototype

Outcome: current repo ingestion works predictably.

Tasks:

- Fix schema/type drift.
- Fix branch field or remove it temporarily.
- Fix delta propagation.
- Fix tests or mark stale suites explicitly.
- Add `/health`.
- Add integration test for active routes.
- Add a small smoke test for `/ingest/github`, `/search`, docs upload, and docs
  relevance.

### Phase 1: Durable Jobs and Branch Snapshots

Outcome: branch-aware ingestion works manually.

Tasks:

- Add jobs table and queue.
- Add repository/branch/snapshot tables.
- Add branch-aware clone/fetch.
- Add snapshot IDs to files/symbols/summaries/embeddings.
- Add branch selector UI.
- Keep SQLite as worker scratch or snapshot export if useful.

### Phase 2: GitHub App and Webhooks

Outcome: selected branches update on push.

Tasks:

- Add GitHub App install flow.
- Store installations.
- Generate installation tokens server-side.
- Wire webhook receiver to durable queue.
- Dedupe deliveries.
- Enqueue branch sync only for tracked branches.
- Show sync state in UI.

### Phase 3: Google Drive Connector

Outcome: selected Drive folders are indexed and linked.

Tasks:

- Add Google OAuth.
- Add Drive folder picker.
- Store Drive connections/folders/files/revisions.
- Implement initial crawl.
- Implement changes cursor and watch renewal.
- Export Docs/Sheets/Slides/text/PDF.
- Chunk, summarize, embed, and tag docs.
- Display document tags and source links.

### Phase 4: LSP Broker

Outcome: semantic indexing supports many languages.

Tasks:

- Add language server catalog.
- Add isolated worker runtime.
- Implement LSP client/broker.
- Normalize symbols, references, hovers, diagnostics.
- Keep Tree-sitter fallback.
- Add language-specific smoke fixtures.
- Replace Tree-sitter+SCIP mapping as the primary semantic path.

### Phase 5: Search and MCP Code Mode

Outcome: agents can progressively discover and query the whole API through a
small MCP surface.

Tasks:

- Add central hybrid search.
- Add file/symbol/doc/finding read APIs.
- Add sandboxed Code Mode MCP with `search()` and `execute()`.
- Define typed SDK.
- Add result caps and audit logs.
- Add per-user/repo/branch scopes.

### Phase 6: Background Agents

Outcome: system continuously creates reviewable engineering findings.

Tasks:

- Add agent run tables and tool call logs.
- Implement refactor/security/schema/test/docs catalogers.
- Add finding UI.
- Add dedupe/fingerprint logic.
- Add user controls for schedules and scopes.
- Add optional issue/PR creation integrations.

## Acceptance Criteria

The target system is not complete until these are true:

1. A signed-in user can connect GitHub through an app installation.
2. The user can select a repository and one or more branches.
3. Each selected branch gets an initial indexed snapshot.
4. A push to a selected branch enqueues exactly one update job per head commit.
5. The user can switch branches in the UI without losing repo context.
6. Search results are scoped to the selected branch/snapshot.
7. A signed-in user can connect Google Drive and choose a folder.
8. Drive docs are exported, chunked, summarized, embedded, tagged, and linked
   back to Drive.
9. Relevant docs show 3-5 tags and source links.
10. LSP indexing supports at least TypeScript/JavaScript, Python, Go, Rust, and
    Java in smoke tests.
11. Tree-sitter remains available as fallback/chunking.
12. MCP exposes `search()` and `execute()` only for broad API access.
13. MCP tool execution is sandboxed, scoped, capped, and audited.
14. Foreground agents can perform multiple parallel searches and at least one
    follow-up retrieval pass.
15. Background agents persist findings with evidence and confidence.
16. No route reads another user's repo, branch, document, chat, or finding.
17. Jobs and webhook deliveries survive restarts.
18. Schema definitions are generated or tested to prevent Python/TypeScript
    drift.

