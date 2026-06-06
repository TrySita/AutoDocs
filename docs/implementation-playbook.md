# Implementation Playbook

Research date: 2026-06-03

This document answers the next layer of product and implementation questions:
best-fit languages, traversal, parsing, MCP/tools, refactor/security tasks,
documentation, preferred documentation structure, summary correction,
go-to-definition UI, cleaner UX, embeddings/indexes, coding practices,
blast-radius checks, review bot integration, cost tracking, model routing,
LSP-first indexing, language support detection, intra/inter-repo graphs,
effective README/agent harness generation, and mining repeated developer tasks
into reusable skills.

## Source Context

Primary sources consulted:

- LSP 3.17 specification:
  https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
- MCP tools/resources/prompts specification:
  https://modelcontextprotocol.io/specification/2025-06-18/server/tools
  https://modelcontextprotocol.io/specification/2025-06-18/server/index
- pgvector README:
  https://github.com/pgvector/pgvector
- Qdrant indexing and search docs:
  https://qdrant.tech/documentation/manage-data/indexing/
  https://qdrant.tech/documentation/search/
- GitHub Checks API and pull request review APIs:
  https://docs.github.com/en/rest/checks/runs
  https://docs.github.com/en/rest/pulls/reviews
  https://docs.github.com/en/rest/pulls/comments
- OpenRouter usage accounting and models API:
  https://openrouter.ai/docs/use-cases/usage-accounting
  https://openrouter.ai/docs/overview/models
  https://openrouter.ai/docs/features/provider-routing
  https://openrouter.ai/docs/features/structured-outputs
- Claude Code memory / `CLAUDE.md`:
  https://code.claude.com/docs/en/memory
- Cursor project rules:
  https://docs.cursor.com/context/rules
- GitHub Copilot repository custom instructions:
  https://docs.github.com/en/copilot/concepts/prompting/response-customization
- OpenAI Codex `AGENTS.md` guide:
  https://github.com/openai/codex/blob/main/docs/agents_md.md

## Short Answer

Use a mixed stack:

- Rust for ingestion workers, LSP broker, graph engine, hash invalidation,
  search orchestration, MCP sandbox host, and high-throughput webhook workers.
- TypeScript for the Next.js UI, admin surfaces, generated clients, Slack UI
  glue, and integration setup screens.
- Postgres + pgvector for the primary database and first vector index.
- Qdrant only when vector volume/filtering/performance outgrows pgvector.
- LSP as the primary code intelligence source, not Tree-sitter or SCIP.
- Tree-sitter only as optional fallback/chunking, not the semantic source of
  truth.
- MCP as a compact Code Mode interface with `search()` and `execute()`, plus
  resources/prompts where useful.
- A hash-driven regeneration DAG to avoid recomputing unchanged code, docs,
  summaries, tags, embeddings, findings, and skills.

The core user-facing product should be a branch-aware engineering knowledge
graph with a clean UI and agent harness generator.

## Best-Fit Programming Languages

### Rust

Rust is the best fit for performance-critical and correctness-critical backend
systems:

- Git sync and content hashing
- LSP broker and language server lifecycle
- graph construction and traversal
- dependency invalidation
- vector/search orchestration API
- webhook normalization workers
- MCP Code Mode sandbox host
- background agent scheduler
- queue workers

Why Rust fits:

- strong type system for provider schemas and normalized events
- safe concurrency
- predictable memory behavior
- efficient graph/hash workloads
- smaller containers than Python-heavy workers
- good fit for long-running services

Recommended crates/classes of tooling:

- async runtime: Tokio
- HTTP API: Axum
- Postgres: SQLx or SeaORM
- queues: Redis/NATS/SQS client depending on deployment
- Git: `git2`/libgit2 or shelling to Git in sandboxed workers when needed
- JSON schema: schemars/serde
- LSP client: custom JSON-RPC client or existing LSP crates
- WASM/V8 sandbox: Wasmtime or a V8 isolate layer depending on Code Mode
  implementation

### TypeScript

TypeScript is best for:

- Next.js web UI
- tRPC or generated API clients
- integration configuration screens
- Slack app interactivity, modals, and command handlers if using Slack SDKs
- shared client-side types
- UI-side graph visualizations

TypeScript should not own high-volume indexing, graph traversal, or LSP worker
execution if end-product performance is prioritized.

### Python

Python is useful for:

- migration from current ingestion system
- experiments
- eval notebooks
- one-off model analysis
- possibly some ML/reranking prototypes

Long-term production should not depend on Python for the hot path unless there
is a specific library advantage.

### SQL

SQL is a first-class implementation language here:

- authorization filters
- branch/snapshot scoping
- summary/embedding joins
- cost aggregation
- read models
- dedupe queries
- findings dashboards

Do not hide all business logic in application code if SQL can express it more
clearly and atomically.

## Best Traversal Method

No single traversal is enough. Use layered traversal.

### Traversal Layers

1. Filesystem traversal
   Finds files, manifests, configs, docs, package roots, service roots.

2. Manifest traversal
   Walks package manifests, lockfiles, workspace files, build files, Docker
   files, compose files, Kubernetes manifests, Terraform files.

3. LSP symbol traversal
   Discovers document symbols, workspace symbols, definitions, references,
   implementations, type definitions, hovers, and diagnostics.

4. Dependency graph traversal
   Builds symbol, file, package, service, and repo dependency graphs.

5. Runtime/config traversal
   Connects services through env vars, URLs, ports, queues, DB names, service
   discovery config, OpenAPI specs, protobufs, GraphQL schemas, and event names.

6. Change traversal
   Starts from a diff and walks dependents, tests, docs, configs, services,
   tickets, and prior incidents.

7. Agent task traversal
   Starts from user intent, searches likely entities, expands graph neighbors,
   reads exact spans, then synthesizes.

### Practical Traversal Order

For initial ingestion:

```text
repo root
  -> manifests/configs
  -> service roots
  -> language workspaces
  -> files
  -> LSP symbols
  -> references
  -> dependency graph
  -> summaries
  -> embeddings
  -> docs/readme/agent harness
```

For a code change:

```text
changed files
  -> changed symbols
  -> direct references
  -> reverse dependents
  -> owning services/packages
  -> tests
  -> docs
  -> tickets/incidents
  -> review findings
```

For a user question:

```text
question
  -> lexical parse: names, paths, tickets, providers
  -> parallel search: symbol/path/vector/docs/findings
  -> graph expansion
  -> exact span reads
  -> answer with citations
```

## Best Parsing Method

Use LSP-first indexing.

Tree-sitter is good syntax infrastructure. SCIP is good when an indexer exists
and works for the repo. But for the product target, LSP is the right primary
semantic layer because it generalizes across languages and supports go to
definition, references, diagnostics, hovers, workspace symbols, and type
information through one protocol.

### LSP Methods to Use

Minimum methods:

- `initialize`
- `initialized`
- `shutdown`
- `textDocument/didOpen`
- `textDocument/documentSymbol`
- `workspace/symbol`
- `textDocument/definition`
- `textDocument/references`
- `textDocument/implementation`
- `textDocument/typeDefinition`
- `textDocument/hover`
- diagnostics via publish diagnostics or pull diagnostics where supported

Optional methods:

- `textDocument/semanticTokens`
- `textDocument/codeAction`
- `textDocument/rename`
- `workspace/executeCommand`

Only read-only methods should be enabled in the first version. Mutating methods
belong behind separate explicit permissions.

### LSP Indexing Pipeline

```text
detect language/workspace
  -> start language server
  -> wait for initialization/indexing readiness
  -> open documents
  -> collect document symbols
  -> collect hovers/docs/signatures
  -> collect diagnostics
  -> collect references/definitions
  -> normalize into code_symbols and symbol_edges
  -> persist source ranges and stable symbol keys
```

### Removing Tree-sitter and SCIP

If you want to effectively remove Tree-sitter and SCIP:

1. Replace Tree-sitter definition extraction with `documentSymbol`.
2. Replace SCIP references with `textDocument/references`.
3. Replace SCIP symbol mapping with LSP locations and normalized symbol keys.
4. Replace Tree-sitter import extraction with LSP references plus manifest
   parsing and static import regex fallback only where needed.
5. Keep a tiny lexical parser for unsupported files and docs/code blocks.

You may still keep Tree-sitter as optional fallback. But the data model should
not depend on Tree-sitter capture names or SCIP occurrence mapping.

## Supported Language Detection

Supported language detection should be explicit, explainable, and visible in
the UI.

### Language Catalog

Create a catalog:

```json
{
  "typescript": {
    "extensions": [".ts", ".tsx", ".js", ".jsx"],
    "markers": ["package.json", "tsconfig.json", "jsconfig.json"],
    "languageServer": "typescript-language-server",
    "capabilities": ["documentSymbol", "definition", "references", "hover", "diagnostics"],
    "status": "supported"
  },
  "python": {
    "extensions": [".py"],
    "markers": ["pyproject.toml", "requirements.txt", "setup.py"],
    "languageServer": "pyright-langserver",
    "capabilities": ["documentSymbol", "definition", "references", "hover", "diagnostics"],
    "status": "supported"
  }
}
```

Initial strong language set:

- TypeScript/JavaScript
- Python
- Go
- Rust
- Java
- C/C++
- C#

Next set:

- Ruby
- PHP
- Swift
- Kotlin
- Dart

### Detection Algorithm

1. Scan file extensions.
2. Scan root and nested manifests.
3. Detect workspaces.
4. Match language server availability.
5. Run a capability probe.
6. Mark language as:
   - `fully_supported`
   - `partially_supported`
   - `syntax_only`
   - `unsupported`

Show this in the UI:

```text
TypeScript: full semantic indexing
Python: full semantic indexing
Ruby: syntax only, no references
Unknown binary files: skipped
```

## MCP and Tools

Use MCP for external agent access, but keep the tool surface small.

### Recommended MCP Surface

Expose:

- `search({ code })`
- `execute({ code })`

Optional MCP server features:

- Resources for stable links to files, symbols, docs, findings, and readme
  guidance.
- Prompts for common tasks such as "review blast radius" or "draft README".

### Code Mode SDK

The model writes code against a typed SDK:

```ts
sdk.search.hybrid(...)
sdk.search.symbols(...)
sdk.files.read(...)
sdk.symbols.references(...)
sdk.graph.blastRadius(...)
sdk.docs.related(...)
sdk.findings.list(...)
sdk.harness.instructions(...)
sdk.skills.search(...)
```

This is better than exposing dozens of tools because:

- lower context cost
- easier composition
- parallel queries inside one execution
- server-side auth remains central
- new API methods do not require huge MCP tool descriptions

### Tool Safety

Every SDK call must enforce:

- user/org identity
- repo/branch/snapshot scope
- Slack channel scope if invoked from Slack
- result caps
- audit logs
- read vs write permission

Generated code must run in a sandbox with no filesystem, no env access, no
arbitrary network access, and strict time/memory/output limits.

## Refactor, Secure, and Cleanup Tasks

The system should provide these tasks as findings, not as vague suggestions.

### Finding Pipeline

```text
index codebase
  -> static rules
  -> graph metrics
  -> summary/finding model
  -> evidence spans
  -> confidence score
  -> dedupe fingerprint
  -> finding record
  -> UI/review bot/Slack delivery
```

### Finding Types

Refactor:

- duplicated code
- oversized files
- cyclic dependencies
- unstable module boundaries
- weak abstractions
- dead code
- unclear ownership

Security:

- wildcard CORS
- missing webhook verification
- exposed secrets
- SSRF paths
- unsafe file operations
- auth bypass
- missing permission checks
- prompt injection risk
- insecure token storage

Cleanup:

- stale comments
- schema drift
- test drift
- unused routes/components
- inconsistent naming
- deprecated dependencies
- generated artifacts committed accidentally

### Finding Schema

```sql
create table findings (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  branch_id uuid,
  snapshot_id uuid,
  finding_type text not null,
  severity text not null,
  confidence numeric not null,
  title text not null,
  description text not null,
  evidence jsonb not null,
  affected_entities jsonb not null,
  recommendation text not null,
  fingerprint text not null,
  status text not null default 'open',
  estimated_effort text,
  estimated_risk text,
  model_policy_id uuid,
  cost_usd numeric,
  created_at timestamptz not null default now(),
  unique (snapshot_id, fingerprint)
);
```

## How It Documents Code Well

Good documentation generation needs a documentation profile, not one generic
prompt.

### Documentation Profile

```sql
create table documentation_profiles (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  name text not null,
  audience text not null,
  style text not null,
  structure jsonb not null,
  examples jsonb not null default '[]',
  anti_examples jsonb not null default '[]',
  created_at timestamptz not null default now()
);
```

Profile example:

```json
{
  "audience": "senior engineers joining the repo",
  "style": "direct, dense, implementation-focused",
  "structure": {
    "fileSummary": ["purpose", "key exports", "data flow", "side effects", "gotchas"],
    "readme": ["what it is", "quick start", "architecture", "common workflows", "ops", "troubleshooting"]
  },
  "avoid": ["marketing copy", "generic explanations", "uncited claims"]
}
```

### Summary Correction Feedback

When the user says "this summary is wrong":

1. Store feedback.
2. Link it to the summary, entity, prompt version, model, and input hash.
3. Classify correction type.
4. Regenerate the summary with the correction.
5. Update the documentation profile if it reflects a reusable preference.

```sql
create table summary_feedback (
  id uuid primary key,
  org_id uuid not null,
  summary_id uuid not null,
  entity_type text not null,
  entity_id uuid not null,
  user_id uuid,
  feedback_type text not null check (feedback_type in ('incorrect_fact', 'missing_detail', 'wrong_tone', 'too_long', 'too_short', 'bad_structure', 'bad_citation')),
  feedback_text text not null,
  correction_text text,
  applied boolean not null default false,
  created_at timestamptz not null default now()
);
```

Repeated corrections become profile rules:

- "Prefer call-flow diagrams for service files."
- "Always mention env vars in deployment docs."
- "Do not call internal APIs public."

## Go To Definition in UI Mode

Go-to-definition should be a first-class navigation primitive.

### Stored Location

Every symbol has:

- file ID
- path
- start/end range
- selection range
- branch/snapshot
- stable symbol key

Every reference edge has:

- source file/range
- target symbol ID if resolved
- target URI if unresolved/external

### UI Flow

From source code:

```text
click symbol
  -> locate token/range
  -> call /definition?file_id&line&character&snapshot
  -> route to target file
  -> scroll to selection range
  -> highlight symbol
  -> show hover/evidence drawer
```

From summaries:

```text
click citation chip
  -> open file/source/doc/ticket/message
  -> scroll/highlight exact span
```

From graph:

```text
click graph node
  -> open entity drawer
  -> jump to source or related docs
```

Routes should encode stable location:

```text
/repo/{repo}/branch/{branch}/source?file={file_id}&symbol={symbol_id}
/repo/{repo}/snapshot/{snapshot}/source?path=src/api/main.py&line=82
```

Use snapshot IDs for historical exactness and branch names for current working
navigation.

## Less Cluttered UX

The UI should use progressive disclosure.

### Principles

- One primary focus per screen.
- Evidence in a collapsible drawer.
- Tags as compact chips, not paragraphs.
- Graphs only when they answer the current question.
- Summaries short by default, expandable to full.
- Branch/snapshot status visible but not dominant.
- Search command palette for power users.
- Findings grouped by severity and type.

### Recommended Layout

Repository page:

```text
Header: repo, branch, sync status, search
Left: files/symbols/docs switcher
Center: selected entity
Right: evidence/chat drawer
Bottom/Tab: findings, graph, activity
```

Summary card:

```text
Name
Short summary
[tags]
Top references (3)
Open full summary / source / related docs
```

Do not show all dependency graphs, all definitions, all docs, and chat at once.
Make those modes.

## Embeddings and Index Choice

### Embedding Entities

Embed separate entity types:

- code symbol summary
- file summary
- package/service summary
- README/design sections
- document chunks
- ticket/work item text
- Slack thread summaries
- meeting transcript chunks
- findings
- skills

Do not embed raw entire files as the primary retrieval unit. Raw files are too
large and noisy. Use symbols/chunks/summaries, then read exact source spans.

### Index Choice

Start with pgvector HNSW.

Reasons:

- same database as permissions and metadata
- simpler deployment
- good enough for early and medium scale
- supports HNSW and IVFFlat
- exact search remains possible for small sets

Use Qdrant when:

- vector volume grows large
- filtered vector search dominates latency
- you need more advanced vector features
- you want dedicated vector DB operations

Qdrant's docs describe HNSW as its dense vector index. pgvector supports HNSW
and IVFFlat. There is no need to choose "HNSW++" as a product baseline unless a
specific production vector engine exposes and supports it. Treat HNSW variants
as implementation details of a vector database, not as your app-level storage
format.

### Recommended Retrieval Stack

```text
metadata filter
  -> BM25/FTS exact search
  -> HNSW vector search
  -> graph expansion
  -> rerank
  -> exact span read
  -> answer
```

Hybrid retrieval matters more than the exact ANN algorithm.

### Embedding Schema

```sql
create table embeddings (
  id uuid primary key,
  org_id uuid not null,
  entity_type text not null,
  entity_id uuid not null,
  embedding_kind text not null,
  content_hash text not null,
  model text not null,
  dims integer not null,
  embedding vector(1536),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (entity_type, entity_id, embedding_kind, model, content_hash)
);

create index embeddings_hnsw_idx
  on embeddings
  using hnsw (embedding vector_cosine_ops);

create index embeddings_scope_idx
  on embeddings (org_id, entity_type);
```

For Qdrant, store `org_id`, `repo_id`, `branch_id`, `snapshot_id`,
`entity_type`, and permission metadata as payload indexes.

## Coding Practices Extraction

To give agents coding practices, mine them from:

- existing `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`,
  `.cursor/rules`
- CONTRIBUTING, STYLEGUIDE, DESIGN, ADRs
- lint configs
- formatting configs
- tests
- recurring code review comments
- accepted/rejected PR suggestions
- summary feedback
- repeated developer tasks

Generate:

- repo-wide practices
- path-specific practices
- language-specific practices
- service-specific practices
- test practices
- security practices

Store them as rules:

```sql
create table coding_practices (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  scope_type text not null,
  scope_pattern text,
  title text not null,
  instruction text not null,
  evidence jsonb not null,
  confidence numeric not null,
  source text not null,
  status text not null default 'active',
  created_at timestamptz not null default now()
);
```

Agents retrieve these rules by repo/path/task, not by dumping all rules into
context.

## Blast Radius of Code Changes

Blast radius is a graph query plus heuristics.

### Inputs

- changed files
- changed symbols
- changed public APIs
- changed config/env
- changed schemas
- changed routes/endpoints
- changed package manifests
- changed docs/tickets

### Graph Expansion

Walk:

- direct references
- reverse references
- file dependencies
- package dependencies
- service dependencies
- tests covering changed symbols/files
- docs citing changed symbols
- work items linked to changed entities
- recent incidents/findings touching same area

### Risk Score

Score by:

- public API changed
- schema changed
- auth/security path changed
- cross-service edge changed
- many reverse dependents
- no direct tests
- stale docs
- high-severity prior findings
- production config touched

### Output

For a PR:

```text
Blast radius: medium-high

Changed:
- api/main.py / ingest_github
- schemas.py / IngestRequest

Likely impacted:
- web tRPC project ingestion route
- generated OpenAPI types
- job polling UI
- MCP search hydration

Recommended checks:
- regenerate API types
- run ingestion API integration tests
- manually test Add Repo
- verify branch parameter behavior
```

This can be surfaced in UI, Slack, MCP, or PR checks.

## Code Review Bot Integration

Use a GitHub App.

### Review Surfaces

Checks API:

- overall status
- annotations on files/lines
- summary report
- links to full analysis

PR review comments:

- inline comments for actionable findings
- review summary for blast radius and docs/test recommendations

Issue comments:

- high-level bot comment when inline locations are not available

### Review Flow

```text
pull_request opened/synchronize
  -> verify webhook
  -> create check run queued
  -> fetch diff
  -> map diff to code symbols
  -> run blast radius
  -> run focused findings
  -> post check annotations
  -> optionally create PR review comments
  -> complete check run
```

Rules:

- Do not spam comments.
- Deduplicate by finding fingerprint.
- Update an existing bot comment/check when possible.
- Only inline comment when evidence is precise and actionable.
- Use "request changes" only for high-confidence severe issues.

## Cost Tracking

Track every model and embedding call.

OpenRouter supports usage accounting and generation stats, including tokens and
cost. Store those results per request and aggregate by org, repo, job, model
policy, agent run, and feature.

### Tables

```sql
create table model_policies (
  id uuid primary key,
  org_id uuid,
  name text not null,
  task_type text not null,
  model_candidates text[] not null,
  provider_policy jsonb not null default '{}',
  max_cost_usd numeric,
  max_input_tokens integer,
  max_output_tokens integer,
  structured_output_schema jsonb,
  created_at timestamptz not null default now()
);

create table llm_requests (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  job_id uuid,
  agent_run_id uuid,
  model_policy_id uuid,
  task_type text not null,
  provider text,
  model text not null,
  request_hash text not null,
  response_hash text,
  generation_id text,
  prompt_tokens integer,
  completion_tokens integer,
  reasoning_tokens integer,
  cached_tokens integer,
  cost_usd numeric,
  latency_ms integer,
  status text not null,
  created_at timestamptz not null default now()
);
```

### Granular Model Routing

Route at these levels:

- organization
- repository
- feature
- task type
- entity type
- summary kind
- risk level
- user request mode
- background vs foreground

Example:

```text
tags: cheap structured model
short summaries: fast mid-tier model
full file summaries: stronger model
security findings: strong reasoning model
Slack quick answers: fast model plus limited context
PR review severe issues: strong model and stricter evidence
```

## Intra-Repo Microservice Connections

Detect services inside a repo using:

- Docker Compose
- Kubernetes manifests
- Terraform
- package/workspace roots
- OpenAPI specs
- protobuf/gRPC files
- GraphQL schemas
- env vars and service URLs
- queue/topic names
- database connection names
- ports
- import/package dependencies

Build:

```sql
services
service_endpoints
service_dependencies
service_configs
```

Service edge examples:

- `web -> api` via `INGESTION_API_URL`
- `api -> postgres` via `DATABASE_URL`
- `worker -> queue` via `QUEUE_URL`
- `api -> github` via GitHub App credentials

## Inter-Repo Connections

Connect repos through:

- package dependencies
- internal package registries
- Git submodules
- monorepo workspace references
- API schemas
- service URLs
- protobuf package names
- Terraform/Kubernetes service references
- GitHub/Linear tickets linking multiple repos
- deployment manifests

Use a cross-repo graph:

```sql
create table repo_edges (
  id uuid primary key,
  org_id uuid not null,
  from_repo_id uuid not null,
  to_repo_id uuid not null,
  edge_type text not null,
  evidence jsonb not null,
  confidence numeric not null,
  created_at timestamptz not null default now()
);
```

The agent should be able to answer:

- "If I change this package, which repos are impacted?"
- "Which service owns this endpoint?"
- "Which docs/tickets mention this cross-service dependency?"

## Effective Repo Root README

An effective README answers:

1. What is this repo?
2. Who is it for?
3. What problem does it solve?
4. How do I run it locally?
5. What are the main services/packages?
6. What are the common workflows?
7. What environment variables are required?
8. How do I test it?
9. How do I deploy it?
10. How does data flow through it?
11. What are common failure modes?
12. Where are deeper docs?
13. Who owns it?

Suggested structure:

```text
# Project Name

## Purpose
## Quick Start
## Architecture
## Repository Layout
## Local Development
## Configuration
## Common Workflows
## Testing
## Deployment
## Data Model
## Troubleshooting
## Security Notes
## Agent Guidance
## More Docs
```

The system should generate README from indexed facts, not generic filler. Every
claim should cite source files, configs, or docs internally.

## Agent-Ready Harness

Turning a codebase into an effective harness means generating the docs and
rules that agents need to work safely.

### Harness Files

Generate:

- `README.md`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `CONTRIBUTING.md`
- `TESTING.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `docs/data-model.md`
- `docs/api.md`
- `docs/dependencies.md`
- `docs/known-risks.md`
- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`
- `.cursor/rules/*.mdc`

### Good `AGENTS.md` / `CLAUDE.md`

Should include:

- how to run tests
- how to run app locally
- repo layout
- architecture constraints
- code style
- security rules
- dependency rules
- files/directories to ignore
- generated files policy
- review checklist
- common pitfalls
- where to find deeper docs

Keep root guidance concise. Put path-specific rules in scoped files.

### Harness Generation Workflow

```text
index repo
  -> identify workflows and commands
  -> identify architecture and services
  -> identify tests and generated files
  -> identify coding practices
  -> draft docs/rules
  -> user review
  -> store accepted profile
  -> regenerate on relevant changes
```

## Learning From Wrong Summaries and User Preferences

When users correct output, the system should learn at three levels:

1. Entity-specific correction.
   "This function summary is wrong."

2. Repo documentation preference.
   "For this repo, summaries should include env vars and side effects."

3. Organization style.
   "Our docs should be short, operational, and cite owners."

Store corrections and convert repeated patterns into rules after review.

## Task Deduping and Skill Mining

The system should collect questions/tasks from:

- MCP calls
- Slack mentions
- PR review requests
- UI chat
- Linear/GitHub issue comments
- background agent prompts

### Task Log

```sql
create table developer_tasks (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  source text not null,
  actor_user_id uuid,
  raw_text text not null,
  normalized_text text not null,
  lexical_hash text not null,
  embedding vector(1536),
  task_type text,
  status text not null default 'observed',
  created_at timestamptz not null default now()
);

create table task_clusters (
  id uuid primary key,
  org_id uuid not null,
  repo_id uuid,
  title text not null,
  normalized_intent text not null,
  cluster_type text,
  confidence numeric not null,
  created_at timestamptz not null default now()
);

create table task_cluster_members (
  cluster_id uuid not null references task_clusters(id) on delete cascade,
  task_id uuid not null references developer_tasks(id) on delete cascade,
  match_type text not null,
  score numeric not null,
  primary key (cluster_id, task_id)
);
```

### Deduping Pipeline

1. Normalize text:
   lowercase, strip punctuation, remove boilerplate, stem where useful.

2. Lexical candidate generation:
   Jaccard similarity over token sets or shingles.

3. Scalable lexical dedupe:
   MinHash/LSH for large task sets.

4. Semantic candidate generation:
   embeddings over normalized task intent.

5. LLM-as-judge:
   determine whether tasks are same intent, related intent, or separate.

6. Cluster:
   by repo, code area, task type, and semantic intent.

7. Promote:
   recurring clusters become practices, docs, playbooks, or skills.

### Skill Generation

A skill should include:

- trigger description
- when to use it
- prerequisites
- exact workflow
- commands/tools
- files to inspect
- common mistakes
- expected output
- examples
- tests/verification

Skill scope:

- codebase-specific
- framework-specific
- org-wide
- global template

Promotion rule:

```text
if a cluster appears >= N times,
or across >= M devs,
or causes repeated failures,
then propose a skill.
```

Do not auto-publish skills globally. Propose, review, accept.

## Making It Do Everything Extremely Well

The product quality comes from these loops:

1. Accurate indexing.
   LSP-backed facts, not guesswork.

2. Incremental regeneration.
   Hashes prevent stale or wasteful recomputation.

3. Permission-correct retrieval.
   Every result is scoped before it reaches the model.

4. Evidence-first answers.
   Agents read exact spans after search.

5. Structured outputs.
   Summaries, tags, findings, and skills are schemas, not blobs.

6. Feedback learning.
   Corrections become profile rules.

7. Cost-aware routing.
   Cheap models for cheap tasks, strong models for high-risk synthesis.

8. Reviewable background work.
   Refactor/security/cleanup tasks are findings with evidence.

9. Clean UX.
   Summary first, evidence on demand, graph only when helpful.

10. Agent harness output.
   Every repo gets README/DESIGN/AGENTS/CLAUDE/testing/security docs that make
   future agent work safer.

## Build Order

1. Central Postgres schema with summaries, embeddings, tags, findings, costs.
2. LSP-first indexing for TypeScript/Python/Go/Rust.
3. Hash-based summary and embedding regeneration.
4. Clean repo UI with go-to-definition and evidence drawer.
5. Blast-radius engine.
6. GitHub App PR review bot.
7. Documentation profile and summary feedback.
8. Agent harness generator.
9. MCP Code Mode server.
10. Task clustering and skill mining.

