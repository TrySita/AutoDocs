-- AutoDocs seed schema for Postgres
-- This file initializes the database schema on first container start.
-- It is mounted into /docker-entrypoint-initdb.d by docker-compose.yml,
-- so Postgres runs it exactly once when PGDATA is empty.

-- Safe extension for UUID generation used in several tables
CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

-- Core entities
CREATE TABLE IF NOT EXISTS "user" (
  "id" text PRIMARY KEY NOT NULL,
  "name" text NOT NULL,
  "email" text NOT NULL,
  "email_verified" boolean NOT NULL,
  "image" text,
  "created_at" timestamp NOT NULL,
  "updated_at" timestamp NOT NULL,
  "stripe_customer_id" text,
  CONSTRAINT "user_email_unique" UNIQUE ("email")
);

CREATE TABLE IF NOT EXISTS "organization" (
  "id" text PRIMARY KEY NOT NULL,
  "name" text NOT NULL,
  "slug" text,
  "logo" text,
  "created_at" timestamp NOT NULL,
  "metadata" text,
  CONSTRAINT "organization_slug_unique" UNIQUE ("slug")
);

CREATE TABLE IF NOT EXISTS "session" (
  "id" text PRIMARY KEY NOT NULL,
  "expires_at" timestamp NOT NULL,
  "token" text NOT NULL,
  "created_at" timestamp NOT NULL,
  "updated_at" timestamp NOT NULL,
  "ip_address" text,
  "user_agent" text,
  "user_id" text NOT NULL,
  "active_organization_id" text,
  CONSTRAINT "session_token_unique" UNIQUE ("token")
);

CREATE TABLE IF NOT EXISTS "account" (
  "id" text PRIMARY KEY NOT NULL,
  "account_id" text NOT NULL,
  "provider_id" text NOT NULL,
  "user_id" text NOT NULL,
  "access_token" text,
  "refresh_token" text,
  "id_token" text,
  "access_token_expires_at" timestamp,
  "refresh_token_expires_at" timestamp,
  "scope" text,
  "password" text,
  "created_at" timestamp NOT NULL,
  "updated_at" timestamp NOT NULL
);

CREATE TABLE IF NOT EXISTS "apikey" (
  "id" text PRIMARY KEY NOT NULL,
  "name" text,
  "start" text,
  "prefix" text,
  "key" text NOT NULL,
  "user_id" text NOT NULL,
  "refill_interval" integer,
  "refill_amount" integer,
  "last_refill_at" timestamp,
  "enabled" boolean DEFAULT true,
  "rate_limit_enabled" boolean DEFAULT true,
  "rate_limit_time_window" integer DEFAULT 86400000,
  "rate_limit_max" integer DEFAULT 10,
  "request_count" integer,
  "remaining" integer,
  "last_request" timestamp,
  "expires_at" timestamp,
  "created_at" timestamp NOT NULL,
  "updated_at" timestamp NOT NULL,
  "permissions" text,
  "metadata" text
);

CREATE TABLE IF NOT EXISTS "invitation" (
  "id" text PRIMARY KEY NOT NULL,
  "organization_id" text NOT NULL,
  "email" text NOT NULL,
  "role" text,
  "status" text DEFAULT 'pending' NOT NULL,
  "expires_at" timestamp NOT NULL,
  "inviter_id" text NOT NULL
);

CREATE TABLE IF NOT EXISTS "member" (
  "id" text PRIMARY KEY NOT NULL,
  "organization_id" text NOT NULL,
  "user_id" text NOT NULL,
  "role" text DEFAULT 'member' NOT NULL,
  "created_at" timestamp NOT NULL
);

CREATE TABLE IF NOT EXISTS "rate_limit" (
  "id" text PRIMARY KEY NOT NULL,
  "key" text,
  "count" integer,
  "last_request" bigint
);

CREATE TABLE IF NOT EXISTS "verification" (
  "id" text PRIMARY KEY NOT NULL,
  "identifier" text NOT NULL,
  "value" text NOT NULL,
  "expires_at" timestamp NOT NULL,
  "created_at" timestamp,
  "updated_at" timestamp
);

CREATE TABLE IF NOT EXISTS "subscription" (
  "id" text PRIMARY KEY NOT NULL,
  "plan" text NOT NULL,
  "reference_id" text NOT NULL,
  "stripe_customer_id" text,
  "stripe_subscription_id" text,
  "status" text DEFAULT 'incomplete',
  "period_start" timestamp,
  "period_end" timestamp,
  "cancel_at_period_end" boolean,
  "seats" integer
);

-- Anonymous/visitor tracking
CREATE TABLE IF NOT EXISTS "anonymous_users" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "last_message_date" date,
  "created_at" timestamptz DEFAULT now(),
  "ip_address" text,
  "fingerprint" text,
  CONSTRAINT "anonymous_users_fingerprint_unique" UNIQUE ("fingerprint")
);

-- Public projects directory
CREATE TABLE IF NOT EXISTS "public_projects" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "name" text NOT NULL,
  "slug" text NOT NULL,
  "description" text,
  "repository_url" text,
  "logo_url" text,
  "is_active" boolean DEFAULT true,
  "sort_order" integer DEFAULT 0,
  "created_at" timestamptz DEFAULT now(),
  "updated_at" timestamptz DEFAULT now(),
  "db_url" text,
  "db_key" text,
  "latest_job_id" text,
  "latest_job_status" text,
  CONSTRAINT "public_projects_slug_key" UNIQUE ("slug")
);

-- Private repositories per organization
CREATE TABLE IF NOT EXISTS "repos" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "organization_id" text NOT NULL,
  "name" text NOT NULL,
  "slug" text NOT NULL,
  "description" text,
  "repository_url" text,
  "logo_url" text,
  "is_active" boolean DEFAULT true,
  "sort_order" integer DEFAULT 0,
  "created_at" timestamptz DEFAULT now(),
  "updated_at" timestamptz DEFAULT now(),
  "db_url" text,
  "db_key" text,
  CONSTRAINT "repos_org_slug_unique" UNIQUE ("organization_id", "slug")
);

-- Conversations and messages
CREATE TABLE IF NOT EXISTS "conversations" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" text,
  "summary" text,
  "created_at" timestamptz DEFAULT now(),
  "character_count" integer DEFAULT 0 NOT NULL,
  "anonymous_user_id" uuid,
  "project_id" uuid,
  CONSTRAINT "conversations_user_check" CHECK (
    (("user_id" IS NOT NULL) AND ("anonymous_user_id" IS NULL)) OR
    (("user_id" IS NULL) AND ("anonymous_user_id" IS NOT NULL))
  )
);

CREATE TABLE IF NOT EXISTS "messages" (
  "id" bigserial PRIMARY KEY NOT NULL,
  "conversation_id" uuid,
  "role" text NOT NULL,
  "content" text NOT NULL,
  "thought_content" text,
  "timestamp" timestamptz DEFAULT now(),
  "included_in_context" boolean DEFAULT true,
  "character_count" integer DEFAULT 0 NOT NULL,
  CONSTRAINT "messages_role_check" CHECK ("role" = ANY (ARRAY['user'::text,'assistant'::text]))
);

-- Tokens and limits
CREATE TABLE IF NOT EXISTS "extension_tokens" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" text NOT NULL,
  "token_hash" varchar(64) NOT NULL,
  "name" varchar(255) DEFAULT 'Extension Token',
  "last_used_at" timestamptz,
  "created_at" timestamptz DEFAULT now(),
  "source" varchar(50) DEFAULT 'unknown',
  CONSTRAINT "extension_tokens_token_hash_key" UNIQUE ("token_hash")
);

CREATE TABLE IF NOT EXISTS "message_limits" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "user_id" text,
  "anonymous_user_id" uuid,
  "count" integer NOT NULL,
  "limit" integer NOT NULL,
  "expires_at" timestamp NOT NULL,
  CONSTRAINT "limits_user_check" CHECK (
    (("user_id" IS NOT NULL) AND ("anonymous_user_id" IS NULL)) OR
    (("user_id" IS NULL) AND ("anonymous_user_id" IS NOT NULL))
  )
);

-- Leads (marketing)
CREATE TABLE IF NOT EXISTS "leads" (
  "id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
  "name" varchar(255) NOT NULL,
  "email" varchar(255) NOT NULL,
  "company_url" varchar(500) NOT NULL,
  "phone_number" varchar(50),
  "repository_count" varchar(50) NOT NULL,
  "pain_point" text,
  "created_at" timestamptz DEFAULT now(),
  "updated_at" timestamptz DEFAULT now(),
  CONSTRAINT "leads_email_key" UNIQUE ("email")
);

-- Indexes
CREATE INDEX IF NOT EXISTS "idx_conversations_anonymous_user_id" ON "conversations" USING btree ("anonymous_user_id" uuid_ops);
CREATE INDEX IF NOT EXISTS "idx_conversations_project_id" ON "conversations" USING btree ("project_id" uuid_ops);

-- Foreign keys (added after table creation to avoid dependency ordering issues)
ALTER TABLE "session"
  ADD CONSTRAINT IF NOT EXISTS "session_user_id_user_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "account"
  ADD CONSTRAINT IF NOT EXISTS "account_user_id_user_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "apikey"
  ADD CONSTRAINT IF NOT EXISTS "apikey_user_id_user_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "invitation"
  ADD CONSTRAINT IF NOT EXISTS "invitation_organization_id_organization_id_fk"
  FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id") ON DELETE CASCADE;

ALTER TABLE "invitation"
  ADD CONSTRAINT IF NOT EXISTS "invitation_inviter_id_user_id_fk"
  FOREIGN KEY ("inviter_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "member"
  ADD CONSTRAINT IF NOT EXISTS "member_organization_id_organization_id_fk"
  FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id") ON DELETE CASCADE;

ALTER TABLE "member"
  ADD CONSTRAINT IF NOT EXISTS "member_user_id_user_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "repos"
  ADD CONSTRAINT IF NOT EXISTS "repos_organization_id_organization_id_fk"
  FOREIGN KEY ("organization_id") REFERENCES "public"."organization"("id") ON DELETE CASCADE;

ALTER TABLE "conversations"
  ADD CONSTRAINT IF NOT EXISTS "conversations_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "conversations"
  ADD CONSTRAINT IF NOT EXISTS "conversations_anonymous_user_id_fkey"
  FOREIGN KEY ("anonymous_user_id") REFERENCES "public"."anonymous_users"("id") ON DELETE CASCADE;

ALTER TABLE "conversations"
  ADD CONSTRAINT IF NOT EXISTS "conversations_project_id_fkey"
  FOREIGN KEY ("project_id") REFERENCES "public"."public_projects"("id") ON DELETE SET NULL;

ALTER TABLE "messages"
  ADD CONSTRAINT IF NOT EXISTS "messages_conversation_id_fkey"
  FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id") ON DELETE CASCADE;

ALTER TABLE "extension_tokens"
  ADD CONSTRAINT IF NOT EXISTS "extension_user_id_fkey"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "message_limits"
  ADD CONSTRAINT IF NOT EXISTS "message_limits_user_id_user_id_fk"
  FOREIGN KEY ("user_id") REFERENCES "public"."user"("id") ON DELETE CASCADE;

ALTER TABLE "message_limits"
  ADD CONSTRAINT IF NOT EXISTS "message_limits_anonymous_user_id_anonymous_users_id_fk"
  FOREIGN KEY ("anonymous_user_id") REFERENCES "public"."anonymous_users"("id") ON DELETE CASCADE;

COMMIT;

