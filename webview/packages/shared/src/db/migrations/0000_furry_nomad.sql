-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TYPE "public"."context_type_enum" AS ENUM('file', 'page', 'none');--> statement-breakpoint
CREATE TYPE "public"."extension_type" AS ENUM('vscode', 'chrome', 'slack', 'gmail', 'outlook', 'discord', 'notion', 'linear', 'github_app', 'jetbrains', 'other');--> statement-breakpoint
CREATE TYPE "public"."message_role" AS ENUM('user', 'assistant', 'system');--> statement-breakpoint
CREATE TYPE "public"."plan_type" AS ENUM('free', 'plus', 'enterprise');--> statement-breakpoint
CREATE TYPE "public"."platform_type" AS ENUM('vscode', 'chrome');--> statement-breakpoint
CREATE TYPE "public"."token_state" AS ENUM('active', 'revoked', 'expired');--> statement-breakpoint
CREATE TABLE "leads" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" varchar(255) NOT NULL,
	"email" varchar(255) NOT NULL,
	"company_url" varchar(500) NOT NULL,
	"phone_number" varchar(50),
	"repository_count" varchar(50) NOT NULL,
	"pain_point" text,
	"created_at" timestamp with time zone DEFAULT now(),
	"updated_at" timestamp with time zone DEFAULT now(),
	CONSTRAINT "leads_email_key" UNIQUE("email")
);
--> statement-breakpoint
ALTER TABLE "leads" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "extension_tokens" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid NOT NULL,
	"token_hash" varchar(64) NOT NULL,
	"name" varchar(255) DEFAULT 'Extension Token',
	"last_used_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now(),
	"source" varchar(50) DEFAULT 'unknown',
	CONSTRAINT "extension_tokens_token_hash_key" UNIQUE("token_hash")
);
--> statement-breakpoint
ALTER TABLE "extension_tokens" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "organizations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" varchar(255) NOT NULL,
	"slug" varchar(100) NOT NULL,
	"monthly_message_limit" integer,
	"created_at" timestamp with time zone DEFAULT now(),
	"updated_at" timestamp with time zone DEFAULT now(),
	"plan_type" "plan_type" DEFAULT 'free' NOT NULL,
	CONSTRAINT "organizations_slug_key" UNIQUE("slug")
);
--> statement-breakpoint
ALTER TABLE "organizations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "public_projects" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"slug" text NOT NULL,
	"description" text,
	"repository_url" text,
	"logo_url" text,
	"is_active" boolean DEFAULT true,
	"sort_order" integer DEFAULT 0,
	"created_at" timestamp with time zone DEFAULT now(),
	"updated_at" timestamp with time zone DEFAULT now(),
	"db_url" text,
	"db_key" text,
	CONSTRAINT "public_projects_slug_key" UNIQUE("slug")
);
--> statement-breakpoint
ALTER TABLE "public_projects" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "conversations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid,
	"summary" text,
	"created_at" timestamp with time zone DEFAULT now(),
	"character_count" integer DEFAULT 0 NOT NULL,
	"anonymous_user_id" uuid,
	"project_id" uuid,
	CONSTRAINT "conversations_user_check" CHECK (((user_id IS NOT NULL) AND (anonymous_user_id IS NULL)) OR ((user_id IS NULL) AND (anonymous_user_id IS NOT NULL)))
);
--> statement-breakpoint
ALTER TABLE "conversations" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "anonymous_users" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"organization_id" uuid,
	"message_count" integer DEFAULT 0,
	"last_message_date" date,
	"created_at" timestamp with time zone DEFAULT now(),
	"ip_address" text,
	"fingerprint" text
);
--> statement-breakpoint
ALTER TABLE "anonymous_users" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "messages" (
	"id" bigserial PRIMARY KEY NOT NULL,
	"conversation_id" uuid,
	"role" text NOT NULL,
	"content" text NOT NULL,
	"timestamp" timestamp with time zone DEFAULT now(),
	"included_in_context" boolean DEFAULT true,
	"character_count" integer DEFAULT 0 NOT NULL,
	CONSTRAINT "messages_role_check" CHECK (role = ANY (ARRAY['user'::text, 'assistant'::text]))
);
--> statement-breakpoint
ALTER TABLE "messages" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY NOT NULL,
	"organization_id" uuid,
	"last_message_date" date,
	"created_at" timestamp with time zone DEFAULT now(),
	"updated_at" timestamp with time zone DEFAULT now()
);
--> statement-breakpoint
ALTER TABLE "users" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
CREATE TABLE "daily_message_count" (
	"user_id" uuid,
	"count" integer DEFAULT 0,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now(),
	"id" uuid PRIMARY KEY NOT NULL
);
--> statement-breakpoint
ALTER TABLE "daily_message_count" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "extension_tokens" ADD CONSTRAINT "extension_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "conversations" ADD CONSTRAINT "conversations_anonymous_user_id_fkey" FOREIGN KEY ("anonymous_user_id") REFERENCES "public"."anonymous_users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "conversations" ADD CONSTRAINT "conversations_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "public"."public_projects"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "conversations" ADD CONSTRAINT "conversations_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "anonymous_users" ADD CONSTRAINT "anonymous_users_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "messages" ADD CONSTRAINT "messages_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_organization_id_fkey" FOREIGN KEY ("organization_id") REFERENCES "public"."organizations"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "daily_message_count" ADD CONSTRAINT "daily_message_limits_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE cascade;--> statement-breakpoint
ALTER TABLE "daily_message_count" ADD CONSTRAINT "daily_message_limits_user_id_fkey1" FOREIGN KEY ("user_id") REFERENCES "public"."anonymous_users"("id") ON DELETE cascade ON UPDATE cascade;--> statement-breakpoint
CREATE INDEX "idx_leads_company_url" ON "leads" USING btree ("company_url" text_ops);--> statement-breakpoint
CREATE INDEX "idx_leads_created_at" ON "leads" USING btree ("created_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_leads_email" ON "leads" USING btree ("email" text_ops);--> statement-breakpoint
CREATE INDEX "idx_extension_tokens_hash" ON "extension_tokens" USING btree ("token_hash" text_ops);--> statement-breakpoint
CREATE INDEX "idx_extension_tokens_user" ON "extension_tokens" USING btree ("user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_extension_tokens_user_source" ON "extension_tokens" USING btree ("user_id" text_ops,"source" text_ops);--> statement-breakpoint
CREATE INDEX "idx_organizations_slug" ON "organizations" USING btree ("slug" text_ops);--> statement-breakpoint
CREATE INDEX "idx_conversations_anonymous_user_id" ON "conversations" USING btree ("anonymous_user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_conversations_project_id" ON "conversations" USING btree ("project_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_conversations_user_id" ON "conversations" USING btree ("user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_messages_conversation_id" ON "messages" USING btree ("conversation_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "idx_messages_conversation_timestamp" ON "messages" USING btree ("conversation_id" timestamptz_ops,"timestamp" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "idx_users_last_message_date" ON "users" USING btree ("last_message_date" date_ops);--> statement-breakpoint
CREATE INDEX "idx_users_organization_id" ON "users" USING btree ("organization_id" uuid_ops);--> statement-breakpoint
CREATE POLICY "Anyone can create leads" ON "leads" AS PERMISSIVE FOR INSERT TO public WITH CHECK (true);--> statement-breakpoint
CREATE POLICY "Authenticated users can view leads" ON "leads" AS PERMISSIVE FOR SELECT TO public;--> statement-breakpoint
CREATE POLICY "Authenticated users can update leads" ON "leads" AS PERMISSIVE FOR UPDATE TO public;--> statement-breakpoint
CREATE POLICY "Authenticated users can delete leads" ON "leads" AS PERMISSIVE FOR DELETE TO public;--> statement-breakpoint
CREATE POLICY "Users can view own extension tokens" ON "extension_tokens" AS PERMISSIVE FOR SELECT TO public USING ((auth.uid() = user_id));--> statement-breakpoint
CREATE POLICY "Users can create own extension tokens" ON "extension_tokens" AS PERMISSIVE FOR INSERT TO public;--> statement-breakpoint
CREATE POLICY "Users can update own extension tokens" ON "extension_tokens" AS PERMISSIVE FOR UPDATE TO public;--> statement-breakpoint
CREATE POLICY "Users can delete own extension tokens" ON "extension_tokens" AS PERMISSIVE FOR DELETE TO public;--> statement-breakpoint
CREATE POLICY "Only authenticated users can manage organizations" ON "organizations" AS PERMISSIVE FOR ALL TO public USING ((auth.role() = 'authenticated'::text));--> statement-breakpoint
CREATE POLICY "Public projects are viewable by everyone" ON "public_projects" AS PERMISSIVE FOR SELECT TO public USING ((is_active = true));--> statement-breakpoint
CREATE POLICY "Only authenticated users can manage public projects" ON "public_projects" AS PERMISSIVE FOR ALL TO public;--> statement-breakpoint
CREATE POLICY "Users can manage their own conversations" ON "conversations" AS PERMISSIVE FOR ALL TO public USING ((auth.uid() = user_id));--> statement-breakpoint
CREATE POLICY "Users can manage messages in their own conversations" ON "messages" AS PERMISSIVE FOR ALL TO public USING ((EXISTS ( SELECT 1
   FROM conversations
  WHERE ((conversations.id = messages.conversation_id) AND (conversations.user_id = auth.uid())))));--> statement-breakpoint
CREATE POLICY "Users can view their own profile" ON "users" AS PERMISSIVE FOR SELECT TO public USING ((auth.uid() = id));
*/