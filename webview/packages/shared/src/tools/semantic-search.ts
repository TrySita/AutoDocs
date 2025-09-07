import { getProjectDbConfig } from "../../../../apps/webapp/src/lib/services/project-config";
import { getAnalysisDB } from "../../../../apps/webapp/src/lib/turso-db";
import { SearchQuery, SemanticSearchResult } from "../types";
import type { components } from "../../../../apps/webapp/src/types/api";

// TypeScript types
export type SearchRes = {
  entity_type: "file" | "definition";
  entity_id: number;
  distance: number; // ANN cosine distance from the index
  similarity: number; // 1 - distance (for unit vectors)
};

/**
 * Perform semantic vector search using the ingestion API.
 */
export async function hybridSearch(
  query: string,
  k: number,
  repoSlug: string
): Promise<SearchRes[]> {
  const baseUrl = process.env.INGESTION_API_URL;
  if (!baseUrl) {
    throw new Error("Missing INGESTION_API_URL environment variable");
  }

  const url = `${baseUrl}/search`;

  const payload: components["schemas"]["SemanticSearchRequest"] = {
    repo_slug: repoSlug,
    query,
    mode: "semantic",
    top_k: k || 10,
  };

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `Ingestion API /search failed: ${res.status} ${res.statusText} ${text}`
    );
  }

  const data =
    (await res.json()) as components["schemas"]["SemanticSearchResponse"];

  return (data.results || []).map((r) => {
    const similarity = r.similarity_score ?? 0;
    return {
      entity_type: r.entity_type,
      entity_id: r.entity_id,
      similarity,
      // Convert similarity in [0,1] to a distance-like value for sorting
      distance: 1 - similarity,
    };
  });
}

/**
 * Perform parallel semantic search with individual K values per query
 */
export async function semanticSearch(
  queries: SearchQuery[],
  repoSlug: string
): Promise<SemanticSearchResult[][]> {
  const { dbUrl } = await getProjectDbConfig(repoSlug);

  if (!dbUrl) {
    throw new Error("Missing database configuration");
  }

  const { tursoDb: db, close } = getAnalysisDB(dbUrl);

  try {
    // Perform all searches in parallel with individual K values via ingestion API
    const searchPromises: Promise<SearchRes[]>[] = queries.map((q) =>
      hybridSearch(q.query, q.k || 10, repoSlug)
    );
    const allAnnHits = await Promise.all(searchPromises);

    // Process each query's results in parallel
    const allResults = await Promise.all(
      allAnnHits.map(async (annHits) => {
        // Group hits by entity type for efficient batch fetching
        const fileHits = annHits.filter((hit) => hit.entity_type === "file");
        const definitionHits = annHits.filter(
          (hit) => hit.entity_type === "definition"
        );

        const results: SemanticSearchResult[] = [];

        // Fetch file entities with definitions
        if (fileHits.length > 0) {
          const fileIds = fileHits.map((hit) => hit.entity_id);
          const filesWithDefinitions = await db.query.files.findMany({
            where: (files, { inArray }) => inArray(files.id, fileIds),
            with: {
              definitions: {
                columns: {
                  id: true,
                  name: true,
                  definitionType: true,
                },
              },
            },
          });

          // Map files to results
          for (const hit of fileHits) {
            const file = filesWithDefinitions.find(
              (f) => f.id === hit.entity_id
            );
            if (file) {
              const { definitions, ...fileRest } = file;
              results.push({
                entity_type: hit.entity_type,
                entity_id: hit.entity_id,
                distance: hit.distance,
                similarity: hit.similarity,
                file: {
                  ...fileRest,
                  definitions: definitions.map((def) => ({
                    id: def.id,
                    name: def.name,
                    definitionType: def.definitionType,
                  })),
                },
              });
            }
          }
        }

        // Fetch definition entities with file info
        if (definitionHits.length > 0) {
          const definitionIds = definitionHits.map((hit) => hit.entity_id);
          const definitionsWithFiles = await db.query.definitions.findMany({
            where: (definitions, { inArray }) =>
              inArray(definitions.id, definitionIds),
            with: {
              file: {
                columns: {
                  id: true,
                  filePath: true,
                  language: true,
                },
              },
            },
          });

          // Map definitions to results
          for (const hit of definitionHits) {
            const definition = definitionsWithFiles.find(
              (d) => d.id === hit.entity_id
            );
            if (definition) {
              const { file, ...defRest } = definition;
              results.push({
                entity_type: hit.entity_type,
                entity_id: hit.entity_id,
                distance: hit.distance,
                similarity: hit.similarity,
                definition: {
                  ...defRest,
                  isExported: Number(defRest.isExported), // Convert to number
                  file,
                },
              });
            }
          }
        }

        // Sort results by similarity (highest first)
        results.sort((a, b) => b.similarity - a.similarity);
        return results;
      })
    );

    // Return array of result arrays (one per query)
    return allResults;
  } catch (e) {
    console.error("Error occurred during semantic search:", e);
    throw e;
  } finally {
    close();
  }
}
