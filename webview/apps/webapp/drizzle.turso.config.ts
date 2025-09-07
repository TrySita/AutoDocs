import { config } from "dotenv";
import { defineConfig } from "drizzle-kit";

config({ path: ".env" });

// Local sqlite introspection. Point DRIZZLE_SQLITE_URL to your target DB, e.g.
// DRIZZLE_SQLITE_URL=file:../../my-project.sqlite
export default defineConfig({
  schema: "./src/lib/turso-db/schema.ts",
  out: "./src/lib/turso-db/",
  dialect: "sqlite",
  dbCredentials: {
    url: process.env.DRIZZLE_SQLITE_URL!,
  },
});
