import { createClient } from "@libsql/client";
import { drizzle } from "drizzle-orm/libsql";
import * as relations from "./relations";
import * as schema from "./schema";

export const getAnalysisDB = (url: string) => {
  // Create the libSQL client (works for file:// URLs without token)
  const client = createClient({
    url,
  });

  const db = drizzle(client, {
    schema: { ...schema, ...relations },
  });

  return {
    tursoDb: db,
    close: () => client.close(),
  };
};

// Export types for use in API routes
export type DB = ReturnType<typeof getAnalysisDB>;

// Export table types for use in API responses
export type FileSelect = typeof schema.files.$inferSelect;
export type FileInsert = typeof schema.files.$inferInsert;

export type PackageSelect = typeof schema.packages.$inferSelect;
export type PackageInsert = typeof schema.packages.$inferInsert;

export type DefinitionSelect = typeof schema.definitions.$inferSelect;
export type DefinitionInsert = typeof schema.definitions.$inferInsert;

export type ImportSelect = typeof schema.imports.$inferSelect;
export type ImportInsert = typeof schema.imports.$inferInsert;

export type DefinitionDependencySelect =
  typeof schema.definitionDependencies.$inferSelect;
export type DefinitionDependencyInsert =
  typeof schema.definitionDependencies.$inferInsert;

export type FileDependencySelect = typeof schema.fileDependencies.$inferSelect;
export type FileDependencyInsert = typeof schema.fileDependencies.$inferInsert;

// Re-export schema and relations for convenience
export { relations, schema };
