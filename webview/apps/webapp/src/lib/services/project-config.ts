import path from "node:path";
import { pathToFileURL } from "node:url";

const repoRoot = path.resolve(process.cwd(), "..", "..");
const configuredDir = process.env.ANALYSIS_DB_DIR?.trim();
const baseDir = configuredDir
  ? path.isAbsolute(configuredDir)
    ? configuredDir
    : path.resolve(repoRoot, configuredDir)
  : repoRoot;

// Resolve a local SQLite file path for a given project slug.
// By default, looks for `<repo-root>/<slug>.db`.
// Override base dir with `ANALYSIS_DB_DIR` (absolute or repo-root-relative).
export async function getProjectDbConfig(
  slug: string,
): Promise<{ dbUrl: string | null }> {
  try {
    const dbFilename = `${slug}.db`;
    const dbPath = path.join(baseDir, dbFilename);

    const dbUrl = pathToFileURL(dbPath).href; // e.g. file:///.../slug.db

    return { dbUrl };
  } catch (error) {
    console.error("Error resolving local project database:", error);
    throw error;
  }
}
