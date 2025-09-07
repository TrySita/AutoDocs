import { drizzle, PostgresJsDatabase } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as relations from './migrations/relations';
import * as schema from './migrations/schema';

const isLocal = process.env.NEXT_PUBLIC_IS_DEVELOPMENT == 'true';

const url = process.env.DATABASE_URL || process.env.SUPABASE_DATABASE_URL;
if (!url) {
  throw new Error('DATABASE_URL not set');
}


const client = postgres(url, {
  fetch_types: false,
  debug: isLocal,
});

export const supabaseDb = drizzle(client, {
  schema: {
    ...schema,
    ...relations,
  },
  logger: isLocal,
});

export const closeDb = () => client.end({ timeout: 1 });

export type SupabaseDb = PostgresJsDatabase<typeof schema & typeof relations>;

export type PublicProjectsSelect = typeof schema.publicProjects.$inferSelect;
export type User = typeof schema.user.$inferSelect;
export type AnonymousUser = typeof schema.anonymousUsers.$inferSelect;

export * from './migrations/relations';
export * from './migrations/schema';
