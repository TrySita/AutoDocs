import {
  pgTable,
  foreignKey,
  text,
  integer,
  timestamp,
  boolean,
  unique,
  uuid,
  varchar,
  date,
  check,
  index,
  bigserial,
  bigint,
  pgEnum,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const contextTypeEnum = pgEnum("context_type_enum", [
  "file",
  "page",
  "none",
]);
export const extensionType = pgEnum("extension_type", [
  "vscode",
  "chrome",
  "slack",
  "gmail",
  "outlook",
  "discord",
  "notion",
  "linear",
  "github_app",
  "jetbrains",
  "other",
]);
export const messageRole = pgEnum("message_role", [
  "user",
  "assistant",
  "system",
]);
export const planType = pgEnum("plan_type", ["free", "plus", "enterprise"]);
export const platformType = pgEnum("platform_type", ["vscode", "chrome"]);
export const tokenState = pgEnum("token_state", [
  "active",
  "revoked",
  "expired",
]);

export const apikey = pgTable(
  "apikey",
  {
    id: text().primaryKey().notNull(),
    name: text(),
    start: text(),
    prefix: text(),
    key: text().notNull(),
    userId: text("user_id").notNull(),
    refillInterval: integer("refill_interval"),
    refillAmount: integer("refill_amount"),
    lastRefillAt: timestamp("last_refill_at", { mode: "date" }),
    enabled: boolean().default(true),
    rateLimitEnabled: boolean("rate_limit_enabled").default(true),
    rateLimitTimeWindow: integer("rate_limit_time_window").default(86400000),
    rateLimitMax: integer("rate_limit_max").default(10),
    requestCount: integer("request_count"),
    remaining: integer(),
    lastRequest: timestamp("last_request", { mode: "date" }),
    expiresAt: timestamp("expires_at", { mode: "date" }),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull(),
    permissions: text(),
    metadata: text(),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "apikey_user_id_user_id_fk",
    }).onDelete("cascade"),
  ]
);

export const extensionTokens = pgTable(
  "extension_tokens",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    userId: text("user_id").notNull(),
    tokenHash: varchar("token_hash", { length: 64 }).notNull(),
    name: varchar({ length: 255 }).default("Extension Token"),
    lastUsedAt: timestamp("last_used_at", {
      withTimezone: true,
      mode: "date",
    }),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    source: varchar({ length: 50 }).default("unknown"),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "extension_user_id_fkey",
    }).onDelete("cascade"),
    unique("extension_tokens_token_hash_key").on(table.tokenHash),
  ]
);

export const anonymousUsers = pgTable(
  "anonymous_users",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    lastMessageDate: date("last_message_date"),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    ipAddress: text("ip_address"),
    fingerprint: text(),
  },
  (table) => [
    unique("anonymous_users_fingerprint_unique").on(table.fingerprint),
  ]
);

export const invitation = pgTable(
  "invitation",
  {
    id: text().primaryKey().notNull(),
    organizationId: text("organization_id").notNull(),
    email: text().notNull(),
    role: text(),
    status: text().default("pending").notNull(),
    expiresAt: timestamp("expires_at", { mode: "date" }).notNull(),
    inviterId: text("inviter_id").notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.inviterId],
      foreignColumns: [user.id],
      name: "invitation_inviter_id_user_id_fk",
    }).onDelete("cascade"),
    foreignKey({
      columns: [table.organizationId],
      foreignColumns: [organization.id],
      name: "invitation_organization_id_organization_id_fk",
    }).onDelete("cascade"),
  ]
);

export const member = pgTable(
  "member",
  {
    id: text().primaryKey().notNull(),
    organizationId: text("organization_id").notNull(),
    userId: text("user_id").notNull(),
    role: text().default("member").notNull(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.organizationId],
      foreignColumns: [organization.id],
      name: "member_organization_id_organization_id_fk",
    }).onDelete("cascade"),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "member_user_id_user_id_fk",
    }).onDelete("cascade"),
  ]
);

export const messageLimits = pgTable(
  "message_limits",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    userId: text("user_id"),
    anonymousUserId: uuid("anonymous_user_id"),
    count: integer().notNull(),
    limit: integer().notNull(),
    expiresAt: timestamp("expires_at", { mode: "date" }).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.anonymousUserId],
      foreignColumns: [anonymousUsers.id],
      name: "message_limits_anonymous_user_id_anonymous_users_id_fk",
    }).onDelete("cascade"),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "message_limits_user_id_user_id_fk",
    }).onDelete("cascade"),
    check(
      "limits_user_check",
      sql`((user_id IS NOT NULL) AND (anonymous_user_id IS NULL)) OR ((user_id IS NULL) AND (anonymous_user_id IS NOT NULL))`
    ),
  ]
);

export const leads = pgTable(
  "leads",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    name: varchar({ length: 255 }).notNull(),
    email: varchar({ length: 255 }).notNull(),
    companyUrl: varchar("company_url", { length: 500 }).notNull(),
    phoneNumber: varchar("phone_number", { length: 50 }),
    repositoryCount: varchar("repository_count", { length: 50 }).notNull(),
    painPoint: text("pain_point"),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    updatedAt: timestamp("updated_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
  },
  (table) => [unique("leads_email_key").on(table.email)]
);

export const account = pgTable(
  "account",
  {
    id: text().primaryKey().notNull(),
    accountId: text("account_id").notNull(),
    providerId: text("provider_id").notNull(),
    userId: text("user_id").notNull(),
    accessToken: text("access_token"),
    refreshToken: text("refresh_token"),
    idToken: text("id_token"),
    accessTokenExpiresAt: timestamp("access_token_expires_at", {
      mode: "date",
    }),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at", {
      mode: "date",
    }),
    scope: text(),
    password: text(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "account_user_id_user_id_fk",
    }).onDelete("cascade"),
  ]
);

export const conversations = pgTable(
  "conversations",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    userId: text("user_id"),
    summary: text(),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    characterCount: integer("character_count").default(0).notNull(),
    anonymousUserId: uuid("anonymous_user_id"),
    projectId: uuid("project_id"),
  },
  (table) => [
    index("idx_conversations_anonymous_user_id").using(
      "btree",
      table.anonymousUserId.asc().nullsLast().op("uuid_ops")
    ),
    index("idx_conversations_project_id").using(
      "btree",
      table.projectId.asc().nullsLast().op("uuid_ops")
    ),
    foreignKey({
      columns: [table.anonymousUserId],
      foreignColumns: [anonymousUsers.id],
      name: "conversations_anonymous_user_id_fkey",
    }).onDelete("cascade"),
    foreignKey({
      columns: [table.projectId],
      foreignColumns: [publicProjects.id],
      name: "conversations_project_id_fkey",
    }).onDelete("set null"),
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "conversations_user_id_fkey",
    }).onDelete("cascade"),
    check(
      "conversations_user_check",
      sql`((user_id IS NOT NULL) AND (anonymous_user_id IS NULL)) OR ((user_id IS NULL) AND (anonymous_user_id IS NOT NULL))`
    ),
  ]
);

export const messages = pgTable(
  "messages",
  {
    id: bigserial({ mode: "bigint" }).primaryKey().notNull(),
    conversationId: uuid("conversation_id"),
    role: text().notNull(),
    content: text().notNull(),
    thoughtContent: text("thought_content"),
    timestamp: timestamp({ withTimezone: true, mode: "date" }).defaultNow(),
    includedInContext: boolean("included_in_context").default(true),
    characterCount: integer("character_count").default(0).notNull(),
  },
  (table) => [
    foreignKey({
      columns: [table.conversationId],
      foreignColumns: [conversations.id],
      name: "messages_conversation_id_fkey",
    }).onDelete("cascade"),
    check(
      "messages_role_check",
      sql`role = ANY (ARRAY['user'::text, 'assistant'::text])`
    ),
  ]
);

export const organization = pgTable(
  "organization",
  {
    id: text().primaryKey().notNull(),
    name: text().notNull(),
    slug: text(),
    logo: text(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
    metadata: text(),
  },
  (table) => [unique("organization_slug_unique").on(table.slug)]
);

export const rateLimit = pgTable("rate_limit", {
  id: text().primaryKey().notNull(),
  key: text(),
  count: integer(),
  // You can use { mode: "bigint" } if numbers are exceeding js number limitations
  lastRequest: bigint("last_request", { mode: "number" }),
});

export const repos = pgTable(
  "repos",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    organizationId: text("organization_id").notNull(),
    name: text().notNull(),
    slug: text().notNull(),
    description: text(),
    repositoryUrl: text("repository_url"),
    logoUrl: text("logo_url"),
    isActive: boolean("is_active").default(true),
    sortOrder: integer("sort_order").default(0),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    updatedAt: timestamp("updated_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    dbUrl: text("db_url"),
    dbKey: text("db_key"),
  },
  (table) => [
    foreignKey({
      columns: [table.organizationId],
      foreignColumns: [organization.id],
      name: "repos_organization_id_organization_id_fk",
    }).onDelete("cascade"),
    unique("repos_org_slug_unique").on(table.organizationId, table.slug),
  ]
);

export const subscription = pgTable("subscription", {
  id: text().primaryKey().notNull(),
  plan: text().notNull(),
  referenceId: text("reference_id").notNull(),
  stripeCustomerId: text("stripe_customer_id"),
  stripeSubscriptionId: text("stripe_subscription_id"),
  status: text().default("incomplete"),
  periodStart: timestamp("period_start", { mode: "date" }),
  periodEnd: timestamp("period_end", { mode: "date" }),
  cancelAtPeriodEnd: boolean("cancel_at_period_end"),
  seats: integer(),
});

export const verification = pgTable("verification", {
  id: text().primaryKey().notNull(),
  identifier: text().notNull(),
  value: text().notNull(),
  expiresAt: timestamp("expires_at", { mode: "date" }).notNull(),
  createdAt: timestamp("created_at", { mode: "date" }),
  updatedAt: timestamp("updated_at", { mode: "date" }),
});

export const user = pgTable(
  "user",
  {
    id: text().primaryKey().notNull(),
    name: text().notNull(),
    email: text().notNull(),
    emailVerified: boolean("email_verified").notNull(),
    image: text(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull(),
    stripeCustomerId: text("stripe_customer_id"),
  },
  (table) => [unique("user_email_unique").on(table.email)]
);

export const publicProjects = pgTable(
  "public_projects",
  {
    id: uuid().defaultRandom().primaryKey().notNull(),
    name: text().notNull(),
    slug: text().notNull(),
    description: text(),
    repositoryUrl: text("repository_url"),
    logoUrl: text("logo_url"),
    isActive: boolean("is_active").default(true),
    sortOrder: integer("sort_order").default(0),
    createdAt: timestamp("created_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    updatedAt: timestamp("updated_at", {
      withTimezone: true,
      mode: "date",
    }).defaultNow(),
    dbUrl: text("db_url"),
    dbKey: text("db_key"),
    latestJobId: text("latest_job_id"),
    latestJobStatus: text("latest_job_status"),
  },
  (table) => [unique("public_projects_slug_key").on(table.slug)]
);

export const session = pgTable(
  "session",
  {
    id: text().primaryKey().notNull(),
    expiresAt: timestamp("expires_at", { mode: "date" }).notNull(),
    token: text().notNull(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull(),
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    userId: text("user_id").notNull(),
    activeOrganizationId: text("active_organization_id"),
  },
  (table) => [
    foreignKey({
      columns: [table.userId],
      foreignColumns: [user.id],
      name: "session_user_id_user_id_fk",
    }).onDelete("cascade"),
    unique("session_token_unique").on(table.token),
  ]
);
