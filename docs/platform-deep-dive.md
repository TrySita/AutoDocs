# Platform Deep Dive

Research date: 2026-06-02

This document expands the target design in `docs/ideal-codebase.md` into a
more implementation-ready architecture. It focuses on doing the system right:
schemas, hash-based regeneration, performance, security, model routing,
integration assembly, Slack channel agents, cloud resources, Rust tradeoffs,
and self-deployment.

## Source Context

Primary sources consulted:

- GitHub Apps and installation tokens:
  https://docs.github.com/en/rest/apps/apps
- GitHub webhook events and payloads:
  https://docs.github.com/webhooks/event-payloads
- GitHub Projects and Issues APIs:
  https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project
- Linear API, OAuth, webhooks, and agents:
  https://developers.linear.app/docs
  https://developers.linear.app/docs/oauth/authentication
  https://developers.linear.app/docs/graphql/webhooks
  https://linear.app/developers/agents
- Slack app manifests, OAuth, Events API, app mentions, request signing, and
  messages:
  https://api.slack.com/concepts/manifests
  https://api.slack.com/authentication/oauth-v2
  https://api.slack.com/apis/events-api
  https://api.slack.com/events/app_mention
  https://api.slack.com/authentication/verifying-requests-from-slack
  https://api.slack.com/methods/chat.postMessage
- Google Drive API changes, watches, and exports:
  https://developers.google.com/workspace/drive/api/guides/manage-changes
  https://developers.google.com/drive/api/guides/push
  https://developers.google.com/drive/api/guides/ref-export-formats
- Google Meet API conference records and transcripts:
  https://developers.google.com/meet/api/guides/overview
  https://developers.google.com/meet/api/reference/rest/v2/conferenceRecords.transcripts
- Microsoft Graph OneDrive delta and subscriptions:
  https://learn.microsoft.com/graph/api/driveitem-delta
  https://learn.microsoft.com/graph/change-notifications-overview
- OpenRouter API:
  https://openrouter.ai/docs
  https://openrouter.ai/docs/features/provider-routing
  https://openrouter.ai/docs/features/structured-outputs
- MCP specification:
  https://modelcontextprotocol.io/specification/2025-06-18/basic/index
- LSP 3.17 specification:
  https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/
- pgvector:
  https://github.com/pgvector/pgvector
- FHIR Provenance and AuditEvent:
  https://fhir.hl7.org/fhir/provenance.html
  https://www.hl7.org/fhir/auditevent.html
- PostgreSQL temporal and bitemporal concepts:
  https://wiki.postgresql.org/wiki/SQL2011Temporal
- Delta Lake time travel and table history:
  https://docs.delta.io/2.3.0/delta-batch.html#query-an-older-snapshot-of-a-table-time-travel

Secondary source used for MCP design:

- Cloudflare Code Mode MCP:
  https://blog.cloudflare.com/code-mode-mcp

## Product Thesis

The system should not be just a code documentation app. The durable product is
a permission-aware engineering knowledge graph:

- source code
- branches and commits
- symbols and references
- docs and document chunks
- tickets and project plans
- Slack channel discussions
- meeting transcripts
- summaries and tags
- findings and refactor opportunities
- foreground and background agent runs

The core product problem is not "embed everything". It is "maintain a
high-fidelity, permission-correct, incrementally updated map of engineering
knowledge, then let humans and agents query and act on it."

## Temporal Memory and Verification

For healthcare, regulatory, provider, pharmacy, and company-dataset use cases,
timestamps cannot be a single `created_at` field. The system needs temporal
memory: the ability to answer what was true, when it was true, when the source
said it, when the platform learned it, and what evidence supported it.

FHIR separates provenance and audit concepts: Provenance captures generation or
updating of entities, while AuditEvent captures usage and activity. That split
is the right mental model for this platform too. A fact needs provenance for
where it came from and audit events for how it was accessed or used.

### Required Time Dimensions

Track at least these time dimensions:

- `valid_time`: when the fact applies in the real world.
- `source_time`: when the source system says the fact was created or updated.
- `ingested_at`: when this platform received the fact.
- `system_time`: when this platform believed this version of the fact.
- `published_at`: when an external document/regulation/policy was published.
- `effective_at`: when a regulation, policy, label, contract, or credential
  became effective.

Examples:

- Encounter date is valid time.
- Provider license start/end is valid time.
- EHR allergy update timestamp is source time.
- Pipeline receipt timestamp is ingested time.
- The database version window is system time.
- FDA guidance publication date is published time.
- Regulation effective date is effective time.

### Bitemporal Version Table

Use append-only entity versions with both valid time and system time. Do not
overwrite old facts.

```sql
create table entity_versions (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_id uuid not null,
  entity_type text not null,
  source_system text not null,
  source_record_id text,

  valid_from timestamptz,
  valid_to timestamptz,

  source_created_at timestamptz,
  source_updated_at timestamptz,
  ingested_at timestamptz not null default now(),

  system_from timestamptz not null default now(),
  system_to timestamptz,

  content_hash text not null,
  normalized_hash text,
  provenance_json jsonb not null default '{}',
  payload_json jsonb not null,

  unique (entity_type, entity_id, source_system, source_record_id, content_hash)
);

create index entity_versions_current_idx
  on entity_versions (org_id, entity_type, entity_id)
  where system_to is null;

create index entity_versions_valid_idx
  on entity_versions (org_id, entity_type, valid_from, valid_to);

create index entity_versions_system_idx
  on entity_versions (org_id, entity_type, system_from, system_to);
```

When a source changes:

```text
old version:
  system_to = now()

new version:
  system_from = now()
  system_to = null
```

The old version remains queryable. The platform can answer both "what is true
now?" and "what did we believe then?"

### Temporal Query Modes

Every retrieval path should support explicit temporal modes:

```text
current truth:
  What does the platform believe now?

as-of system time:
  What did the platform believe on a date?

valid-at real-world time:
  What was true for this patient/provider/drug/service on a date?

source-as-of:
  What had the source system reported by a date?

timeline:
  How did this fact/entity change over time?
```

Typical bitemporal predicate:

```sql
where valid_from <= :valid_at
  and (valid_to is null or valid_to > :valid_at)
  and system_from <= :as_of_system_time
  and (system_to is null or system_to > :as_of_system_time)
```

For a lakehouse, Delta Lake time travel or equivalent table-history features
can reconstruct prior table snapshots. That is useful for dataset-level
history, but the product should still store entity-level version intervals so
agents can reason over facts without scanning full historical snapshots.

### Temporal Embeddings

Embeddings should inherit temporal and provenance metadata. A vector match is
not enough; the candidate must be valid for the requested time scope.

```sql
create table temporal_embeddings (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_version_id uuid references entity_versions(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  embedding_kind text not null,
  content_hash text not null,
  model text not null,
  dims integer not null,
  embedding vector(1536),

  valid_from timestamptz,
  valid_to timestamptz,
  system_from timestamptz not null,
  system_to timestamptz,
  source_updated_at timestamptz,
  published_at timestamptz,
  effective_at timestamptz,
  source_authority text,
  permission_hash text,
  metadata jsonb not null default '{}',

  created_at timestamptz not null default now()
);
```

Retrieval flow:

```text
time scope
  -> permission filter
  -> temporal filter
  -> lexical/vector search
  -> provenance/source authority ranking
  -> contradiction search
  -> verifier stack
```

### Old vs New Ranking Policy

Do not globally prefer old over new or new over old. Use an entity-specific
temporal policy.

Examples:

- Clinical current state: prefer newest current valid record from the most
  authoritative source.
- Clinical history: prefer records valid during the clinical event date.
- Claims analysis: prefer records valid on service date and adjudication date.
- Provider credentialing: prefer the license/enrollment/network record valid
  for the requested date.
- Drug labels: prefer latest label for current use, but historical label for
  historical claims or audits.
- Regulations: prefer effective date over ingestion date.
- Company datasets: prefer the dataset version tied to the report, model run,
  or job lineage.

Store ranking policies:

```sql
create table temporal_ranking_policies (
  id uuid primary key,
  org_id uuid references organizations(id) on delete cascade,
  entity_type text not null,
  use_case text not null,
  recency_weight numeric not null default 0,
  source_authority_weight numeric not null default 1,
  valid_time_weight numeric not null default 1,
  effective_time_weight numeric not null default 0,
  contradiction_penalty numeric not null default 1,
  policy_json jsonb not null default '{}',
  unique (org_id, entity_type, use_case)
);
```

Ranking should combine:

```text
semantic relevance
+ lexical relevance
+ source authority
+ temporal fit
+ provenance confidence
- contradiction penalty
- staleness penalty when policy says freshness matters
```

### Temporal Summaries

A summary should be versioned by the input facts and time scope. It should not
make timeless claims when the underlying facts are temporal.

```sql
create table temporal_summary_versions (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  summary_kind text not null,
  time_scope_json jsonb not null,
  source_version_ids uuid[] not null,
  input_hash text not null,
  dependency_hash text not null,
  model text not null,
  summary_text text not null,
  generated_at timestamptz not null default now(),
  unique (entity_type, entity_id, summary_kind, input_hash, dependency_hash)
);
```

For example, a provider summary should say:

```text
Provider X was in-network for Plan Y during 2024-03-01 to 2024-08-31 according
to Source A. The current record as of 2026-06-02 says the provider is no longer
in network.
```

### Claim Extraction

Before verification, convert generated answers into atomic claims.

```json
{
  "claim": "Provider X was in-network for Plan Y on 2024-03-01",
  "entity_refs": [
    { "type": "provider", "id": "..." },
    { "type": "plan", "id": "..." }
  ],
  "required_time": {
    "valid_at": "2024-03-01",
    "as_of_system_time": "2026-06-02T00:00:00Z"
  },
  "required_evidence_type": "provider_network_version",
  "risk_level": "high"
}
```

This makes verification a structured pipeline rather than a second freeform
answer.

### Verifier Stack

Use multiple verifiers. An adversarial LLM is useful, but it is not enough by
itself.

1. Schema verifier.
   Does the answer match the required output schema?

2. Citation verifier.
   Does every factual claim have cited evidence?

3. Temporal verifier.
   Are the cited facts valid for the requested valid/system/effective time?

4. Permission verifier.
   Was every cited source allowed for this user, Slack channel, MCP client, and
   organization policy?

5. Provenance verifier.
   Are the cited sources authoritative enough for the claim?

6. Contradiction verifier.
   Search for overlapping, newer, older, or higher-authority conflicting facts.

7. Numeric/query verifier.
   Rerun SQL or deterministic computations for counts, totals, cohorts, and
   thresholds.

8. Policy verifier.
   Determine whether the answer crosses into clinical, legal, regulatory, or
   compliance advice requiring human review.

9. Adversarial LLM verifier.
   Ask a separate model to find unsupported, stale, contradicted, overbroad, or
   overconfident statements.

10. Human escalation.
   Required for high-risk clinical/regulatory decisions or unresolved
   contradictions.

### Adversarial Verification Flow

```text
agent drafts answer
  -> extract atomic claims
  -> map claims to citations
  -> verify citation support
  -> verify temporal validity
  -> verify permissions
  -> search contradictions
  -> rerun deterministic queries
  -> run adversarial verifier model
  -> revise answer or downgrade confidence
  -> final answer with claims, citations, conflicts, and verifier result
```

Store the verification result:

```sql
create table answer_verifications (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  agent_run_id uuid,
  answer_hash text not null,
  time_scope_json jsonb not null,
  schema_result jsonb not null default '{}',
  citation_result jsonb not null default '{}',
  temporal_result jsonb not null default '{}',
  permission_result jsonb not null default '{}',
  provenance_result jsonb not null default '{}',
  contradiction_result jsonb not null default '{}',
  numeric_result jsonb not null default '{}',
  adversarial_result jsonb not null default '{}',
  final_confidence numeric,
  requires_human_review boolean not null default false,
  created_at timestamptz not null default now()
);
```

### Contradiction Search

For important claims, search:

- same entity and same attribute with overlapping valid time
- same entity and same attribute with newer system time
- same entity and same attribute from a higher-authority source
- regulatory records with later effective dates
- manual corrections
- audit flags or known findings

If a conflict exists, the answer should expose it:

```text
There is conflicting evidence. Source A says active on the requested date.
Source B says inactive beginning that date. Source B has higher authority
because it is the credentialing system of record, so the answer is marked low
confidence pending review.
```

### Final Answer Shape

Internally, an answer should look like:

```json
{
  "answer": "...",
  "time_scope": {
    "valid_at": "2024-03-01",
    "as_of_system_time": "2026-06-02T00:00:00Z"
  },
  "claims": [],
  "citations": [],
  "conflicts": [],
  "verification": {
    "schema": "pass",
    "citations": "pass",
    "temporal": "pass",
    "permissions": "pass",
    "contradictions": "pass_with_notes",
    "adversarial": "pass"
  },
  "confidence": 0.82,
  "requires_human_review": false
}
```

The user may see a simplified version, but the system should persist the
structured result.

### Design Rule

The platform should never answer from memory alone. It should answer from:

```text
retrieved evidence
+ temporal scope
+ provenance
+ permissions
+ contradiction search
+ verifier result
```

Embeddings find candidates. Temporal provenance and verifiers decide whether
the answer is safe to use.

## Target Shape

The clean target system is:

```text
Web UI / Slack / MCP client / API client
  |
  v
API Gateway
  |-- auth
  |-- authorization
  |-- rate limits
  |-- audit
  |-- webhook receivers
  |-- MCP Code Mode server
  |
  v
Core DB: Postgres + pgvector
  |
  +--> Object storage
  +--> Durable queues
  +--> Worker pool
  +--> LSP/indexing sandbox pool
  +--> LLM gateway
```

The system should have four kinds of state:

1. Identity and authorization state.
2. External integration state.
3. Knowledge graph state.
4. Compute/job state.

Separating those makes the product faster, easier to secure, and easier to
extend.

## The Right Database Design

### Core Rules

1. External objects get stable local IDs.
2. External IDs are unique per provider account, not globally.
3. Branch heads are mutable; snapshots are immutable.
4. Content hashes drive regeneration.
5. Permissions are stored separately from embeddings.
6. Embeddings are attached to versioned entities.
7. Summaries are attached to input hashes, not just entity IDs.
8. Agent runs and tool calls are auditable.

### Identity Tables

```sql
create table organizations (
  id uuid primary key,
  slug text not null unique,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table users (
  id uuid primary key,
  email text not null unique,
  name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table organization_memberships (
  org_id uuid not null references organizations(id) on delete cascade,
  user_id uuid not null references users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'member', 'viewer')),
  created_at timestamptz not null default now(),
  primary key (org_id, user_id)
);

create table audit_events (
  id uuid primary key,
  org_id uuid references organizations(id) on delete cascade,
  actor_user_id uuid references users(id) on delete set null,
  actor_external_ref text,
  event_type text not null,
  target_type text not null,
  target_id text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

### Integration Tables

Keep one generic integration layer and provider-specific tables where the
provider has unique behavior.

```sql
create table integration_providers (
  id text primary key,
  category text not null check (category in ('git', 'docs', 'messaging', 'meeting', 'project')),
  display_name text not null,
  capabilities jsonb not null,
  created_at timestamptz not null default now()
);

create table integration_accounts (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null references integration_providers(id),
  external_account_id text not null,
  external_account_name text,
  status text not null default 'active',
  scopes text[] not null default '{}',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (org_id, provider_id, external_account_id)
);

create table integration_credentials (
  id uuid primary key,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  credential_type text not null check (credential_type in ('oauth', 'installation_token_source', 'bot_token', 'api_key')),
  access_token_ciphertext bytea,
  refresh_token_ciphertext bytea,
  private_key_ciphertext bytea,
  expires_at timestamptz,
  key_version text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table external_objects (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null references integration_providers(id),
  integration_account_id uuid references integration_accounts(id) on delete cascade,
  object_type text not null,
  external_id text not null,
  parent_external_id text,
  url text,
  display_name text,
  metadata jsonb not null default '{}',
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (integration_account_id, object_type, external_id)
);

create table sync_cursors (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null references integration_providers(id),
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  scope_key text not null,
  cursor_value text,
  cursor_metadata jsonb not null default '{}',
  last_success_at timestamptz,
  updated_at timestamptz not null default now(),
  unique (integration_account_id, scope_key)
);

create table webhook_deliveries (
  id uuid primary key,
  provider_id text not null references integration_providers(id),
  external_delivery_id text not null,
  event_type text not null,
  integration_account_id uuid references integration_accounts(id) on delete set null,
  payload_hash text not null,
  received_at timestamptz not null default now(),
  processed_at timestamptz,
  status text not null default 'received',
  error text,
  unique (provider_id, external_delivery_id)
);
```

This generic layer lets you add new integrations quickly. Provider-specific
tables remain useful for high-query-volume objects such as repositories,
branches, documents, channels, and tickets.

### Git Tables

```sql
create table git_repositories (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  external_repo_id text not null,
  owner text not null,
  name text not null,
  full_name text not null,
  clone_url text,
  html_url text,
  default_branch text,
  visibility text check (visibility in ('public', 'private', 'internal')),
  archived boolean not null default false,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (integration_account_id, external_repo_id)
);

create table git_branches (
  id uuid primary key,
  repository_id uuid not null references git_repositories(id) on delete cascade,
  branch_name text not null,
  enabled boolean not null default true,
  current_head_sha text,
  last_indexed_sha text,
  last_successful_snapshot_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (repository_id, branch_name)
);

create table source_snapshots (
  id uuid primary key,
  repository_id uuid not null references git_repositories(id) on delete cascade,
  branch_id uuid references git_branches(id) on delete set null,
  commit_sha text not null,
  parent_sha text,
  tree_sha text,
  source_kind text not null default 'git',
  status text not null default 'created',
  indexed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (repository_id, commit_sha)
);

create table source_files (
  id uuid primary key,
  snapshot_id uuid not null references source_snapshots(id) on delete cascade,
  path text not null,
  language text,
  mime_type text,
  blob_sha text,
  content_hash text not null,
  normalized_content_hash text not null,
  size_bytes integer,
  object_key text,
  is_deleted boolean not null default false,
  created_at timestamptz not null default now(),
  unique (snapshot_id, path)
);
```

### Code Intelligence Tables

```sql
create table code_symbols (
  id uuid primary key,
  snapshot_id uuid not null references source_snapshots(id) on delete cascade,
  file_id uuid not null references source_files(id) on delete cascade,
  stable_symbol_key text not null,
  display_name text not null,
  kind text not null,
  container_name text,
  signature text,
  documentation text,
  range_start_line integer not null,
  range_start_col integer not null,
  range_end_line integer not null,
  range_end_col integer not null,
  selection_start_line integer,
  selection_start_col integer,
  selection_end_line integer,
  selection_end_col integer,
  source_hash text not null,
  normalized_source_hash text not null,
  semantic_hash text,
  lsp_payload jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (snapshot_id, stable_symbol_key)
);

create table symbol_edges (
  id uuid primary key,
  snapshot_id uuid not null references source_snapshots(id) on delete cascade,
  source_symbol_id uuid references code_symbols(id) on delete cascade,
  source_file_id uuid not null references source_files(id) on delete cascade,
  target_symbol_id uuid references code_symbols(id) on delete set null,
  target_uri text,
  edge_type text not null check (edge_type in ('reference', 'definition', 'type_definition', 'implementation', 'import', 'inheritance', 'call')),
  confidence numeric not null default 1.0,
  range_start_line integer,
  range_start_col integer,
  range_end_line integer,
  range_end_col integer,
  metadata jsonb not null default '{}'
);

create table diagnostics (
  id uuid primary key,
  snapshot_id uuid not null references source_snapshots(id) on delete cascade,
  file_id uuid not null references source_files(id) on delete cascade,
  source text,
  severity text,
  code text,
  message text not null,
  range_start_line integer,
  range_start_col integer,
  range_end_line integer,
  range_end_col integer,
  metadata jsonb not null default '{}'
);
```

Important: `stable_symbol_key` should not be a line number. It should combine
path, language, container, name, kind, signature, and a normalized source hash.
Line numbers move too easily.

### Documents, Meetings, Messages, and Project Tables

Docs:

```sql
create table documents (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  external_document_id text not null,
  title text not null,
  mime_type text,
  web_url text,
  icon_url text,
  parent_external_id text,
  permission_fingerprint text,
  current_revision_id uuid,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (integration_account_id, external_document_id)
);

create table document_revisions (
  id uuid primary key,
  document_id uuid not null references documents(id) on delete cascade,
  external_revision_id text,
  content_hash text not null,
  exported_mime_type text,
  exported_object_key text,
  exported_at timestamptz,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (document_id, content_hash)
);

create table document_chunks (
  id uuid primary key,
  document_revision_id uuid not null references document_revisions(id) on delete cascade,
  document_id uuid not null references documents(id) on delete cascade,
  chunk_index integer not null,
  chunk_type text not null default 'section',
  heading_path text[],
  text text not null,
  token_count integer,
  content_hash text not null,
  metadata jsonb not null default '{}',
  unique (document_revision_id, chunk_index)
);
```

Messages:

```sql
create table message_channels (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  external_channel_id text not null,
  name text,
  is_private boolean,
  web_url text,
  scope_policy jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (integration_account_id, external_channel_id)
);

create table messages_external (
  id uuid primary key,
  channel_id uuid not null references message_channels(id) on delete cascade,
  external_message_id text not null,
  external_thread_id text,
  sender_external_id text,
  sender_display_name text,
  text text not null,
  message_ts timestamptz,
  permalink text,
  content_hash text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (channel_id, external_message_id)
);
```

Meetings:

```sql
create table meetings (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  external_meeting_id text not null,
  title text,
  start_time timestamptz,
  end_time timestamptz,
  meeting_url text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (integration_account_id, external_meeting_id)
);

create table meeting_transcripts (
  id uuid primary key,
  meeting_id uuid not null references meetings(id) on delete cascade,
  external_transcript_id text,
  transcript_object_key text,
  content_hash text not null,
  language_code text,
  created_at timestamptz not null default now(),
  unique (meeting_id, content_hash)
);

create table meeting_transcript_entries (
  id uuid primary key,
  transcript_id uuid not null references meeting_transcripts(id) on delete cascade,
  entry_index integer not null,
  speaker_name text,
  start_time_offset_ms integer,
  end_time_offset_ms integer,
  text text not null,
  content_hash text not null,
  unique (transcript_id, entry_index)
);
```

Project planning:

```sql
create table work_items (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  provider_id text not null,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  external_item_id text not null,
  source_type text not null check (source_type in ('github_issue', 'github_pr', 'github_project_item', 'linear_issue', 'linear_project')),
  title text not null,
  description text,
  status text,
  priority text,
  assignee_external_id text,
  team_or_project text,
  url text,
  updated_external_at timestamptz,
  content_hash text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (integration_account_id, source_type, external_item_id)
);
```

### Summaries, Tags, References, and Embeddings

Use versioned summary inputs:

```sql
create table summary_inputs (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  summary_kind text not null,
  prompt_version text not null,
  model_policy_id uuid,
  input_hash text not null,
  dependency_hash text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (entity_type, entity_id, summary_kind, prompt_version, input_hash, dependency_hash)
);

create table summaries (
  id uuid primary key,
  summary_input_id uuid not null references summary_inputs(id) on delete cascade,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  summary_kind text not null,
  model text not null,
  provider text,
  text text not null,
  short_text text,
  output_hash text not null,
  token_usage jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table source_references (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  from_entity_type text not null,
  from_entity_id uuid not null,
  to_entity_type text not null,
  to_entity_id uuid not null,
  relation_type text not null,
  relevance_score numeric,
  confidence numeric not null default 1.0,
  evidence jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table summary_citations (
  id uuid primary key,
  summary_id uuid not null references summaries(id) on delete cascade,
  target_entity_type text not null,
  target_entity_id uuid not null,
  label text,
  reason text,
  span jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table tags (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  normalized_tag text not null,
  display_tag text not null,
  description text,
  created_at timestamptz not null default now(),
  unique (org_id, normalized_tag)
);

create table entity_tags (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  tag_id uuid not null references tags(id) on delete cascade,
  score numeric not null,
  source text not null check (source in ('llm', 'rule', 'user', 'imported')),
  evidence_summary text,
  evidence_refs jsonb not null default '[]',
  model text,
  input_hash text,
  created_at timestamptz not null default now(),
  unique (entity_type, entity_id, tag_id, input_hash)
);

create table embeddings (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
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
```

This makes tags and citations first-class. A UI can show a summary and the
small chips next to it because tags, source references, and citations are not
buried inside freeform model text.

## Hash-Based Regeneration System

### Hash Levels

Use several hashes. A single content hash is not enough.

`raw_hash`:

- Exact bytes.
- Detects any file/document change.
- Used for storage dedupe.

`normalized_hash`:

- Content after line ending normalization, whitespace policy, comment policy
  where appropriate.
- Avoids regenerating when formatting changes are irrelevant.

`structure_hash`:

- AST/LSP symbol outline, headings, table structure, or transcript speaker/time
  structure.
- Detects changes in shape even when some text shifts.

`semantic_input_hash`:

- Text that will be sent to the model.
- Includes selected code/doc chunk content, dependency summaries, prompt
  version, and relevant metadata.

`dependency_hash`:

- Ordered hash of referenced symbols/docs/tickets/messages that are included in
  the summary input.
- Changes when a dependency summary changes, even if the entity itself did not.

`permission_hash`:

- Hash of provider permission state relevant to an entity.
- Used to invalidate search visibility and Slack/channel references.

`embedding_hash`:

- Hash of the exact text embedded plus model ID and dimensions.

`finding_fingerprint`:

- Stable hash of finding type, affected entity stable key, rule/agent version,
  and normalized evidence.

### Entity Hash Strategy

Code file:

```text
raw_hash = sha256(bytes)
normalized_hash = sha256(normalize_line_endings(bytes))
structure_hash = sha256(language + sorted(symbol stable keys + ranges + kinds))
```

Code symbol:

```text
source_hash = sha256(exact symbol source)
normalized_source_hash = sha256(strip_comments_or_normalize_ws(symbol source))
semantic_hash = sha256(signature + public docs + dependency stable keys)
```

Document chunk:

```text
content_hash = sha256(text)
structure_hash = sha256(heading_path + chunk_type + table schema)
```

Slack message:

```text
content_hash = sha256(normalized text + sender + timestamp + thread id)
```

Meeting transcript:

```text
content_hash = sha256(entries speaker + offsets + text)
```

Work item:

```text
content_hash = sha256(title + description + status + assignee + labels + comments if included)
```

### Regeneration DAG

Maintain a dependency graph across entities:

```text
code_symbol -> referenced code_symbol
code_file -> contained code_symbol
summary -> summary_input
summary_input -> dependency summaries
document -> document_chunks
tag -> summary/document/chunk
finding -> evidence entities
agent answer -> citations/evidence
```

When an entity changes:

1. Compute new hashes.
2. If `raw_hash` changed but `normalized_hash` did not, skip semantic
   regeneration unless the view needs exact source.
3. If `normalized_hash` changed, regenerate the entity's summaries and
   embeddings.
4. If a summary output hash changed, propagate invalidation to dependents.
5. If the output hash did not change, stop propagation.
6. If permissions changed, invalidate search visibility and Slack/doc
   references, but do not regenerate text unless the summary included restricted
   content that should no longer be exposed.

### Work Queue Keys

Dedup jobs by deterministic keys:

```text
index:snapshot:{snapshot_id}
summarize:{entity_type}:{entity_id}:{summary_kind}:{input_hash}:{dependency_hash}
embed:{entity_type}:{entity_id}:{embedding_kind}:{model}:{content_hash}
tags:{entity_type}:{entity_id}:{input_hash}
finding:{agent_type}:{snapshot_id}:{scope_hash}
```

The queue should reject duplicate pending jobs with the same key.

### Summary Input Contract

For every summary, persist a compact input record:

```json
{
  "entity": { "type": "code_symbol", "id": "..." },
  "prompt_version": "symbol-summary-v4",
  "model_policy": "technical-summarizer",
  "content_hash": "...",
  "dependency_hash": "...",
  "citations": [
    { "type": "code_symbol", "id": "...", "reason": "direct reference" },
    { "type": "document_chunk", "id": "...", "reason": "linked design doc" }
  ],
  "input_sections": [
    { "name": "source", "hash": "..." },
    { "name": "dependency_summaries", "hash": "..." },
    { "name": "related_docs", "hash": "..." }
  ]
}
```

This makes regeneration debuggable.

## How to Make It Fast

### Fast Ingestion

Use staged indexing:

1. Cheap file scan and hashes.
2. Git diff or provider delta.
3. Language detection.
4. Tree-sitter chunking for changed files.
5. LSP semantic indexing for changed workspaces.
6. Graph update.
7. Summary invalidation.
8. Batched embeddings.
9. Background findings.

Do not run LSP, summaries, and embeddings for unchanged content.

### Git Optimization

Use:

- shallow fetch for first sync where possible
- partial clone or blobless clone for large repos if language servers can still
  work
- worktrees per branch/snapshot in workers
- object cache per repository
- content hash reuse across branches
- commit graph to avoid re-indexing known commits

For GitHub, the webhook gives branch ref and before/after SHAs. Use that to
enqueue precise branch work. For GitLab/Bitbucket later, normalize their push
events to the same internal event type.

### LSP Optimization

Use:

- one worker pool per language family
- warm language server images
- dependency cache volumes
- lockfile hash as dependency cache key
- project root grouping
- file-open batching
- timeouts per language server operation
- fallback to Tree-sitter when LSP is not ready

Persist enough LSP output to avoid asking the same hover/reference question
twice for unchanged symbols.

### Summary and Embedding Optimization

Use:

- summary input hashes
- prompt prefix caching where provider supports it
- batch embeddings
- rerank only top candidate pools
- small model for tags and short summaries
- stronger model only for synthesis or complex findings
- output schema validation and retry only failed records
- token budgets by entity type
- queue priority: user-visible sync before background cataloging

### Query Optimization

Search should run in stages:

1. Metadata filters: org, repo, branch, snapshot, provider, permissions.
2. Lexical/BM25 search for exact names, paths, ticket IDs, and channel terms.
3. Vector search for semantic intent.
4. Graph expansion around top code symbols/docs/tickets.
5. Reranking.
6. Answer generation from a capped evidence set.

Use materialized views or denormalized read tables for common UI surfaces:

- repo file tree
- branch latest snapshot
- entity search index
- recent findings
- document tags
- channel scopes

### Cache Layers

- CDN/static cache for web assets.
- API response cache for read-only metadata.
- Redis for short-lived job locks and rate counters.
- Postgres materialized views for read models.
- Object storage for blobs and exported docs.
- LSP dependency cache for workers.
- Model response cache keyed by summary input hash.

## Security Model

### Authorization Principle

Every answer and search result must pass the intersection of:

- user's app role
- provider grant
- repo/document/ticket/channel permissions
- selected channel scope if answering in Slack
- MCP token scope
- organization policy

Do not rely on embeddings for security. Embeddings can retrieve candidates, but
the final result set must be filtered by authorization metadata.

### OAuth and Token Security

Use:

- OAuth state and PKCE where applicable.
- encrypted refresh/access tokens.
- KMS-managed envelope encryption.
- short-lived GitHub installation tokens.
- token rotation and revocation handling.
- per-provider scope records.
- audit events for token use.

Never send provider tokens to model prompts or sandboxed MCP code.

### Webhook Security

For every provider:

- verify signatures when provider supports it
- dedupe delivery IDs
- store payload hash
- respond quickly
- process asynchronously
- log validation failures
- rate-limit by provider/account

GitHub and Slack both support request signing. Drive and Microsoft change
notifications require verification/validation patterns and should be treated as
change triggers, with durable delta/change APIs as source of truth.

### Slack-Specific Security

Slack channel agent responses need extra care:

- Map Slack user IDs to app users when possible.
- If a Slack user is not linked, answer only from channel-public scoped data or
  prompt them to link account.
- Channel scope must explicitly select repos/docs/projects the agent may use.
- For private channels, only ingest messages where the bot is a member.
- Respond with ephemeral messages for permission errors.
- Do not quote private docs into a channel unless channel policy allows it.
- Store Slack event IDs for idempotency.

### MCP Security

Code Mode MCP must:

- authenticate clients
- authorize repo/branch/doc scopes
- run code in a sandbox
- disallow environment access
- disallow filesystem access
- disallow arbitrary network access
- cap CPU, memory, wall time, and output size
- audit code and SDK calls
- keep write operations separate and explicitly permissioned

### Prompt Injection and Data Exfiltration

Docs, Slack messages, and meeting transcripts can contain malicious instructions.
Treat all external content as untrusted.

Mitigations:

- hard system/developer prompt boundaries
- retrieval-time source labels
- instruction hierarchy in prompts
- no secrets in context
- output filtering
- action confirmation for writes
- sandboxed tool execution
- audit and anomaly detection for unusual retrieval/write patterns

## Cleaner Views and Reference Tags

### Product Navigation

Recommended top-level views:

- Home
- Repositories
- Documents
- Channels
- Meetings
- Work Items
- Findings
- Agents
- Settings

### Repository View

Layout:

- left: file tree and symbol search
- top: repo, branch, snapshot, sync health
- center tabs: Docs, Source, Graph, Findings, Related Docs, Activity
- right: evidence drawer or chat

Do not make the user choose between code and docs. The useful view is
"selected code entity plus related knowledge."

### Summary With Reference Chips

Every summary card should show:

```text
Title / symbol / file / doc
Short summary
Tags: [auth] [webhook] [branch sync] [risk: security]
References:
  [Design Doc] one-line summary, confidence, link
  [Linear ENG-123] one-line summary, status
  [Slack #platform] one-line message/thread summary
  [Meeting 2026-05-29] decision summary
Actions:
  Open source | Open doc | Ask follow-up | Create finding
```

Reference chips are backed by `source_references`, `summary_citations`, and
`entity_tags`.

### Tag Ranking

For each entity, generate more than 5 candidate tags but display only 3-5.

Rank by:

- confidence
- source type weight
- query relevance
- recency
- user pinning
- whether tag appears across related entities

Tag sources:

- LLM extraction from summaries.
- Rules for obvious labels: language, framework, provider, risk type.
- User-defined tags.
- Imported labels from Linear/GitHub/Drive where applicable.

### Views by Source Type

Code:

- symbols, file summaries, dependencies, diagnostics, tests, findings.

Docs:

- document summary, tags, chunks, code references, owner/revision.

Slack:

- channel scope, relevant threads, decisions, unresolved questions.

Meetings:

- transcript summary, decisions, action items, linked docs/tickets/code.

Work items:

- status, assignee, labels, linked code/docs/messages/findings.

## OpenRouter Model Strategy

### Why OpenRouter Helps

OpenRouter gives a single OpenAI-compatible API surface for many model
providers. That is useful for:

- model fallback
- provider routing
- cost controls
- comparing models
- structured outputs with compatible models
- separating cheap tagging from stronger synthesis

### Model Policy Table

Add:

```sql
create table model_policies (
  id uuid primary key,
  org_id uuid references organizations(id) on delete cascade,
  name text not null,
  task_type text not null,
  provider_preference jsonb not null default '{}',
  model_candidates text[] not null,
  max_input_tokens integer,
  max_output_tokens integer,
  max_cost_usd numeric,
  require_structured_output boolean not null default false,
  temperature numeric not null default 0,
  created_at timestamptz not null default now(),
  unique (org_id, name)
);

create table llm_requests (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  model_policy_id uuid references model_policies(id) on delete set null,
  task_type text not null,
  provider text,
  model text not null,
  request_hash text not null,
  response_hash text,
  status text not null,
  token_usage jsonb not null default '{}',
  cost_usd numeric,
  latency_ms integer,
  error text,
  created_at timestamptz not null default now()
);
```

### Recommended Task Routing

Tags:

- cheap, fast model.
- strict JSON schema.
- low max output tokens.

Short summaries:

- mid-tier fast model.
- structured output.
- retry if schema invalid.

Full technical summaries:

- stronger model.
- include citations and dependency summaries.

Foreground Q&A:

- strong reasoning model for synthesis.
- fast model for query planning can be separate.

Background findings:

- strong model for final finding generation.
- static analysis/rules first, LLM second.

### Structured Outputs

Use JSON schemas for:

- tags
- summary outputs
- finding outputs
- meeting action items
- Slack answer citations
- integration extraction results

Do not parse summaries with ad hoc tags like `<gist>`. Store structured output
and render it.

### Fallback Policy

For each task:

1. Try preferred model/provider.
2. If provider unavailable, try fallback.
3. If structured output unsupported, route to a model that supports it.
4. If output schema fails, retry once with repair prompt.
5. If still invalid, store failed request and continue pipeline where possible.

For sensitive enterprise tenants, support a policy that denies providers that
train on prompts or lack required privacy posture.

## Should This Be Written in Rust?

If development time is not the constraint and end-product quality is the main
goal, use Rust for the core backend services that benefit from performance,
correctness, and predictable operations.

### Best Rust Targets

Use Rust for:

- integration event normalizer
- durable worker runtime
- Git sync and content hashing
- LSP broker
- dependency graph construction
- hash invalidation engine
- search API and reranking orchestration
- sandbox host for MCP Code Mode
- high-throughput webhook receiver
- background agent scheduler

Why:

- strong type system helps schema-heavy integration work
- memory safety
- lower latency and lower resource use
- good concurrency
- good fit for parsers, hashes, graph algorithms, and long-running workers
- easier to package workers as small containers

### Keep TypeScript For

- Next.js web app
- UI
- Slack app surface if using Slack's Node SDK heavily
- integration admin screens
- typed client SDK generation

### Python's Role

Python is convenient for AI experimentation and current ingestion. Long term,
it can be reduced to:

- prototyping
- model/eval notebooks
- maybe specialized ML tasks

But the production LLM gateway can be Rust or TypeScript because OpenRouter and
OpenAI-compatible APIs are HTTP JSON.

### Recommended End-State Language Split

```text
TypeScript:
  web app, UI, API route adapters if Next remains, generated clients

Rust:
  API services, worker services, LSP broker, Git sync, graph engine,
  integration normalizer, MCP sandbox host

SQL:
  Postgres schema, materialized read models

Python:
  optional eval tooling, migration period for existing ingestion
```

This gives the end product stronger reliability without forcing the frontend
and integration UI into Rust.

## Integration Assembly Framework

### Connector Contract

Every connector should implement the same lifecycle:

```text
manifest
auth_start
auth_callback
refresh_credentials
list_scopes
initial_sync
delta_sync
webhook_verify
webhook_normalize
normalize_object
extract_text
map_permissions
actions
health_check
```

Connector manifest:

```json
{
  "id": "slack",
  "category": "messaging",
  "displayName": "Slack",
  "auth": {
    "type": "oauth2",
    "scopes": ["app_mentions:read", "chat:write", "channels:history"]
  },
  "webhooks": {
    "signature": "slack-signing-secret",
    "events": ["app_mention", "message.channels"]
  },
  "resources": ["workspace", "channel", "message", "thread"],
  "actions": ["post_message", "post_thread_reply"],
  "sync": {
    "cursorType": "timestamp",
    "supportsDelta": true
  }
}
```

### Normalized Event Types

All provider webhooks should normalize into:

```text
git.push
git.branch.deleted
git.repository.updated
project.item.created
project.item.updated
project.comment.created
doc.file.created
doc.file.updated
doc.file.deleted
message.created
message.updated
meeting.transcript.available
integration.installed
integration.uninstalled
permission.changed
```

Then the rest of the system does not care if the event came from GitHub,
Linear, Slack, Google Drive, OneDrive, or a future provider.

### Provider-Specific Starts

Git:

- GitHub first.
- Add GitLab and Bitbucket by implementing normalized repo, branch, commit,
  PR, issue, and webhook events.

Project:

- Linear first.
- GitHub Issues/Projects first or second because it is tightly related to
  repos.
- Jira/Trello/Asana later through same work item schema.

Messaging:

- Slack first.
- Microsoft Teams later.

Meetings:

- Google Meet first for transcript ingestion if Workspace plan/API access
  supports it.
- Microsoft Teams/Zoom later.

Docs:

- Google Drive first.
- OneDrive/SharePoint second through Microsoft Graph.

## GitHub and Linear

### GitHub

Use GitHub App for:

- repository access
- installation-scoped tokens
- webhooks
- selected repository permissions

Index:

- repositories
- branches
- commits
- pull requests
- issues
- project items if using GitHub Projects
- comments where relevant

Key webhook events:

- installation
- installation_repositories
- push
- repository
- pull_request
- issues
- project_v2_item if using Projects events where available

### Linear

Use Linear OAuth for user/workspace auth and Linear webhooks for updates.
Linear is GraphQL-centered, so the connector should store GraphQL IDs and
normalize:

- teams
- users
- issues
- projects
- comments
- labels
- cycles
- statuses

Linear's agent concepts are also relevant: Linear agents can be mentionable or
assignable in Linear. That suggests a future "AutoDocs agent in Linear" path:

- mention the agent on an issue
- ask it to connect code/docs context
- have it add a comment with citations
- optionally assign work to the agent if the product supports autonomous PRs

Start with read and comment. Do not start with autonomous issue mutation.

## Slack Channel Agent

### Installation

Create a Slack app with:

- bot token
- Events API
- app mentions
- message events where needed
- slash commands
- interactivity
- request signing

Minimum scopes depend on exact behavior, but likely:

- `app_mentions:read`
- `chat:write`
- `channels:read`
- `channels:history` for public channel message ingestion
- `groups:read` and `groups:history` if private channels are supported
- `im:history` only if direct messages are supported

### Channel Scope Model

Add:

```sql
create table slack_channel_agents (
  id uuid primary key,
  org_id uuid not null references organizations(id) on delete cascade,
  integration_account_id uuid not null references integration_accounts(id) on delete cascade,
  channel_id uuid not null references message_channels(id) on delete cascade,
  enabled boolean not null default true,
  default_repo_id uuid,
  default_branch_id uuid,
  policy jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique (channel_id)
);

create table channel_knowledge_scopes (
  id uuid primary key,
  channel_agent_id uuid not null references slack_channel_agents(id) on delete cascade,
  scope_type text not null check (scope_type in ('repo', 'branch', 'document_folder', 'project', 'meeting')),
  scope_id uuid not null,
  access_mode text not null default 'read',
  created_at timestamptz not null default now(),
  unique (channel_agent_id, scope_type, scope_id)
);
```

A Slack channel can reference only the repos/docs/projects explicitly attached
to that channel, further filtered by the requesting user's app permissions.

### Slack Interaction Flow

```text
User mentions @AutoDocs in #platform
  -> Slack sends app_mention event
  -> verify Slack signature
  -> dedupe event ID
  -> enqueue slack_agent_request
  -> respond 200 quickly

Worker:
  -> load team/channel/user/thread
  -> map Slack user to AutoDocs user if linked
  -> load channel knowledge scopes
  -> run agent search across allowed repos/docs/tickets/messages
  -> post threaded reply with citations
```

If the question needs private data and the Slack user is not linked:

- post an ephemeral "link your account" prompt
- do not answer from private repo/docs

### Referencing the Agent

Supported commands:

- `@AutoDocs where is branch sync implemented?`
- `@AutoDocs summarize the latest auth findings`
- `/autodocs ask <question>`
- `/autodocs connect repo owner/name --branch main`
- `/autodocs connect drive-folder <folder>`
- `/autodocs scope list`
- `/autodocs findings`

For long answers, reply in thread and include:

- direct answer
- citations
- tags
- links to full web view

## Google Meet

Google Meet should be treated as a meeting artifact source, not a live bot
target at first.

Target ingestion:

- conference records
- transcripts
- transcript entries
- recordings metadata if available and permitted
- participants metadata where permitted

Flow:

```text
Meet transcript available
  -> sync conference record
  -> fetch transcript metadata
  -> fetch transcript entries
  -> chunk transcript by topic/time/speaker
  -> summarize decisions/action items
  -> link action items to Linear/GitHub work items when possible
  -> embed transcript chunks
```

Important limitation:

- Google Meet API is not the same as adding a Slack-like bot into a channel.
  Treat it as asynchronous transcript ingestion unless a separate live meeting
  bot product is built.

## Google Drive and OneDrive

### Google Drive

Use:

- OAuth account connection.
- folder picker.
- changes API cursors.
- push notifications as invalidation.
- export for Google-native Docs/Sheets/Slides.

Store:

- Drive file ID
- folder ID
- mime type
- webViewLink
- iconLink
- revision/version
- modified time
- permission fingerprint
- exported content hash

### OneDrive / SharePoint

Use Microsoft Graph:

- OAuth through Microsoft identity platform.
- driveItem delta for changes.
- subscriptions for change notifications.
- download URLs or content APIs for files.
- SharePoint/OneDrive permission metadata.

Normalize into the same `documents`, `document_revisions`, and
`document_chunks` tables.

### Docs Tooling Differences

Google Drive:

- Google-native files require export.
- changes API provides page tokens.
- push channels expire and need renewal.

OneDrive:

- Microsoft Graph delta links represent sync state.
- subscriptions are change notifications.
- SharePoint site/document library boundaries matter.

The connector framework should hide those differences behind:

```text
initial_sync_folder
delta_sync_folder
fetch_document_revision
extract_text
map_permissions
```

## Deployment Options

### Self-Hosted Minimal Stack

Use Docker Compose:

- web app
- API gateway
- worker
- Postgres with pgvector
- Redis or NATS for queues
- MinIO for object storage
- Caddy or Traefik for TLS/reverse proxy
- optional Qdrant if not using pgvector

This is the "deploy it ourselves" starting point.

```text
docker compose up
  web: Next.js
  api: Rust/Node/Python API
  worker: ingestion/index jobs
  postgres: metadata + pgvector
  redis: queue/locks/cache
  minio: blobs
  caddy: TLS
```

Minimum production-ish VM:

- 4 vCPU
- 16 GB RAM
- fast SSD
- separate disk or managed Postgres strongly preferred

LSP workers can be memory-heavy. For larger repos, run them on separate worker
nodes.

### Managed AWS Stack

Good production baseline:

- ECS Fargate or EKS for containers
- RDS Postgres with pgvector
- S3 for object storage
- SQS for queues
- EventBridge Scheduler for recurring sync
- Secrets Manager + KMS for secrets
- ElastiCache Redis for locks/rate limits/cache
- ALB + WAF for ingress
- CloudWatch/OpenTelemetry for logs/traces
- VPC private subnets for DB/workers

Use separate services:

- web
- API
- webhook receiver
- worker-general
- worker-lsp
- worker-agent
- MCP gateway

### Managed GCP Stack

- Cloud Run or GKE
- Cloud SQL Postgres
- Cloud Storage
- Pub/Sub
- Secret Manager
- Cloud Scheduler
- Cloud Logging/Trace

GCP is attractive if Google Workspace integrations are central, but the stack is
not locked to GCP.

### Managed Azure Stack

- Azure Container Apps or AKS
- Azure Database for PostgreSQL
- Blob Storage
- Service Bus
- Key Vault
- Application Gateway/WAF
- Azure Monitor

Azure is attractive if OneDrive/Teams/Microsoft Graph is central.

### Cloudflare Role

Cloudflare is useful for:

- edge auth/gateway
- WAF
- static assets
- R2 object storage
- Queues
- Workers for lightweight MCP gateway
- Durable Objects for session-like coordination

But LSP indexing needs containers and real filesystem/process support, so do
not put the entire system on Workers.

## Self-Deployment Plan

Phase 1: Docker Compose

1. Add Postgres + pgvector.
2. Add Redis/NATS.
3. Add MinIO.
4. Split API and worker.
5. Move local SQLite analysis into Postgres or keep SQLite as worker scratch.
6. Add migrations.
7. Add `.env.example` for all integrations.
8. Add backup/restore docs.

Phase 2: Single-cloud deployment

1. Pick AWS/GCP/Azure.
2. Containerize web, API, workers.
3. Provision managed Postgres.
4. Provision object storage.
5. Provision queue.
6. Provision secrets.
7. Add Terraform or Pulumi.
8. Add CI/CD.
9. Add logs/traces/metrics.

Phase 3: Scale

1. Separate LSP worker pool.
2. Add autoscaling by queue depth.
3. Add read replicas if needed.
4. Add vector index tuning.
5. Add per-tenant rate limits.
6. Add region strategy.

## Performance and Scale Targets

Initial target:

- small repo initial sync: under 2 minutes excluding model calls
- medium repo initial sync: under 15 minutes
- push incremental sync: under 2 minutes for small diffs
- Slack answer latency: initial ack under 3 seconds, final threaded answer
  under 30 seconds for normal questions
- docs delta sync: under 5 minutes from notification/cursor processing

Scale levers:

- cache unchanged hashes
- split workers by job type
- batch embeddings
- route cheap model work separately
- cap background agents
- use queue priority
- precompute read views
- apply branch/snapshot filters before vector search

## Observability

Track:

- webhook delivery count/failure
- queue depth by job type
- job latency and retry count
- LSP startup and operation latency
- model latency/cost/token usage
- embedding throughput
- search latency by stage
- Slack event ack latency
- permission-denied answer count
- cache hit rate by hash type
- summary invalidation fanout

Add trace IDs from webhook to job to summary/embedding/agent answer.

## What to Build First

The highest-leverage build order:

1. Durable jobs and central Postgres schema.
2. GitHub App repository/branch sync.
3. Hash-based source file and symbol regeneration.
4. Summary/embedding schema with input hashes.
5. Google Drive folder sync and document tags.
6. Slack channel agent with scoped repos/docs.
7. Linear/GitHub Issues work item ingestion.
8. OneDrive connector using the same doc adapter.
9. LSP broker expansion.
10. Code Mode MCP.
11. Background findings agents.

Do not build every integration first. Build the integration framework with two
providers in different categories, then add the rest:

- GitHub for git/project.
- Google Drive for docs.
- Slack for messaging.
- Linear for project planning.

If the framework handles those four cleanly, OneDrive, GitHub Projects, Google
Meet, GitLab, Bitbucket, Jira, and Teams become much easier.

## Key Design Decisions

1. Use Postgres + pgvector as the primary product DB.
2. Keep SQLite only as local/scratch/export.
3. Use content hashes and summary input hashes for regeneration.
4. Store tags, citations, references, summaries, embeddings separately.
5. Use Rust for core workers/index/search if optimizing the end product.
6. Keep TypeScript for web and frontend-facing integration code.
7. Use OpenRouter through a model policy layer, not scattered env vars.
8. Treat Slack as a scoped channel agent, not an unrestricted chatbot.
9. Treat Google Meet as transcript ingestion first.
10. Build connectors from a manifest and normalized event/object contract.
11. Sandbox MCP Code Mode.
12. Make all UI and agent answers permission-filtered.
