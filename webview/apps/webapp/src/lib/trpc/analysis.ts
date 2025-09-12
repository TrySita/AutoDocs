import { getProjectDbConfig } from "@/lib/services/project-config";
import { definitions, files, packages } from "@/lib/turso-db/schema";
import { desc, eq, inArray } from "drizzle-orm";
import { z } from "zod";
import { getAnalysisDB } from "../turso-db";
import { publicProcedure, router } from "./init";

// Input validation schemas
const paginationSchema = z.object({
  offset: z.number().min(0).default(0),
  projectSlug: z.string(),
});

const filesQuerySchema = paginationSchema.extend({
  language: z.string().optional(),
});

const projectIdSchema = z.object({
  projectSlug: z.string(),
});

const fileByIdSchema = z.object({
  id: z.number(),
  projectSlug: z.string(),
});

const fileByPathSchema = z.object({
  path: z.string(),
  projectSlug: z.string(),
});

const definitionByIdSchema = z.object({
  id: z.number(),
  projectSlug: z.string(),
});

const definitionBatchSchema = z.object({
  ids: z.array(z.number()),
  projectSlug: z.string(),
});

const searchQuerySchema = z.object({
  projectSlug: z.string(),
  q: z.string().min(1),
  limit: z.number().min(1).max(50).default(10),
  offset: z.number().min(0).default(0),
});

// Response schemas to match Python API structure
export const analysisRouter = router({
  // Search endpoints (FTS)
  search: router({
    files: publicProcedure.input(searchQuerySchema).query(async ({ input }) => {
      const { q, limit, offset, projectSlug } = input;
      const { dbUrl } = await getProjectDbConfig(projectSlug);

      if (!dbUrl) {
        throw new Error("Project database configuration not found");
      }

      const { client, close } = getAnalysisDB(dbUrl);

      try {
        // Simple prefix query using FTS5 (prefix indexes enabled in ingestion)
        const match = `${q.trim()}*`;
        const res = await client.execute({
          sql: `
            SELECT f.id as id,
                   f.file_path as filePath,
                   f.language as language
            FROM files_path_fts fts
            JOIN files f ON fts.rowid = f.id
            WHERE files_path_fts MATCH ?
            LIMIT ? OFFSET ?
          `,
          args: [match, limit, offset],
        });

        // libsql returns rows as objects already
        return res.rows;
      } finally {
        close();
      }
    }),

    definitions: publicProcedure
      .input(searchQuerySchema)
      .query(async ({ input }) => {
        const { q, limit, offset, projectSlug } = input;
        const { dbUrl } = await getProjectDbConfig(projectSlug);

        if (!dbUrl) {
          throw new Error("Project database configuration not found");
        }

        const { client, close } = getAnalysisDB(dbUrl);

        try {
          const match = `${q.trim()}*`;
          const res = await client.execute({
            sql: `
              SELECT d.id as id,
                     d.name as name,
                     d.definition_type as definitionType,
                     d.file_id as fileId,
                     f.id as file_id,
                     f.file_path as file_path
              FROM definitions_name_fts fts
              JOIN definitions d ON fts.rowid = d.id
              JOIN files f ON f.id = d.file_id
              WHERE definitions_name_fts MATCH ?
              LIMIT ? OFFSET ?
            `,
            args: [match, limit, offset],
          });
          const rows = res.rows;

          return rows.map((r) => ({
            id: r.id,
            name: r.name,
            definitionType: r.definitionType,
            fileId: r.fileId,
            file: { id: r.file_id, filePath: r.file_path },
          }));
        } finally {
          close();
        }
      }),
  }),
  // Files endpoints
  files: router({
    list: publicProcedure.input(filesQuerySchema).query(async ({ input }) => {
      const { offset, language, projectSlug } = input;

      const { dbUrl } = await getProjectDbConfig(projectSlug);

      if (!dbUrl) {
        throw new Error("Project database configuration not found");
      }

      const { tursoDb: db, close } = getAnalysisDB(dbUrl);

      try {
        // Use Drizzle's relations to efficiently fetch files with definitions
        const filesResult = await db.query.files.findMany({
          where: language ? eq(files.language, language) : undefined,
          orderBy: desc(files.createdAt),
          offset,
        });

        // Transform to match the expected API structure
        return filesResult;
      } finally {
        close();
      }
    }),

    byId: publicProcedure.input(fileByIdSchema).query(async ({ input }) => {
      const { id, projectSlug } = input;

      const { dbUrl } = await getProjectDbConfig(projectSlug);

      if (!dbUrl) {
        throw new Error("Project database configuration not found");
      }

      const { tursoDb: db, close } = getAnalysisDB(dbUrl);

      try {
        // Use Drizzle's relations to efficiently fetch file with all related data
        const file = await db.query.files.findFirst({
          where: eq(files.id, id),
          columns: {
            id: true,
            filePath: true,
            language: true,
            aiSummary: true,
            aiShortSummary: true,
            fileContent: true,
          },
          with: {
            definitions: {
              with: {
                references_sourceDefinitionId: true,
                file: {
                  columns: {
                    id: true,
                    filePath: true, // keep it small
                    language: true,
                  },
                },
              },
            },
            fileDependencies_fromFileId: {
              with: {
                file_toFileId: true,
              },
            },
            fileDependencies_toFileId: {
              with: {
                file_fromFileId: true,
              },
            },
          },
        });

        if (!file) {
          throw new Error("File not found");
        }

        const {
          fileDependencies_fromFileId: fileDependencies,
          fileDependencies_toFileId: fileDependents,
          definitions,
          ...rest
        } = file;

        // Transform to match the expected API structure
        return {
          ...rest,
          fileDependencies,
          fileDependents,
          definitions,
        };
      } finally {
        close();
      }
    }),
    idForFilePath: publicProcedure
      .input(fileByPathSchema)
      .query(async ({ input, ctx }) => {
        const { path, projectSlug } = input;

        const { dbUrl } = await getProjectDbConfig(projectSlug);

        if (!dbUrl) {
          throw new Error("Project database configuration not found");
        }

        const { tursoDb: db, close } = getAnalysisDB(dbUrl);

        try {
          // Use Drizzle's relations to efficiently fetch file with all related data
          const file = await db.query.files.findFirst({
            where: eq(files.filePath, path),
            columns: {
              id: true,
            },
          });

          if (!file) {
            throw new Error("File not found");
          }

          // Transform to match the expected API structure
          return file;
        } finally {
          close();
        }
      }),
  }),

  // Definitions endpoints
  definitions: router({
    batch: publicProcedure
      .input(definitionBatchSchema)
      .query(async ({ input, ctx }) => {
        const { ids, projectSlug } = input;

        const { dbUrl } = await getProjectDbConfig(projectSlug);

        if (!dbUrl) {
          throw new Error("Project database configuration not found");
        }

        const { tursoDb: db, close } = getAnalysisDB(dbUrl);

        try {
          if (ids.length === 0) {
            return [];
          }

          const definitionsWithRelations = await db.query.definitions.findMany({
            where: inArray(definitions.id, ids),
            // root definition columns
            columns: {
              id: true,
              name: true,
              definitionType: true,
              fileId: true,
            },
            with: {
              file: {
                columns: {
                  id: true,
                  filePath: true, // keep it small
                  language: true,
                },
              },
              definitionDependencies_fromDefinitionId: {
                columns: {
                  id: true,
                  fromDefinitionId: true,
                  toDefinitionId: true,
                },
                with: {
                  definition_toDefinitionId: {
                    columns: {
                      id: true,
                      name: true,
                      definitionType: true,
                      fileId: true,
                    },
                    with: {
                      file: { columns: { id: true, filePath: true } },
                    },
                  },
                },
              },
              definitionDependencies_toDefinitionId: {
                columns: {
                  id: true,
                  fromDefinitionId: true,
                  toDefinitionId: true,
                },
                with: {
                  definition_fromDefinitionId: {
                    columns: {
                      id: true,
                      name: true,
                      definitionType: true,
                      fileId: true,
                    },
                    with: {
                      file: { columns: { id: true, filePath: true } },
                    },
                  },
                },
              },
            },
          });

          // Transform to match the expected API structure
          return definitionsWithRelations.map((def) => {
            const {
              definitionDependencies_fromDefinitionId: definitionDependencies,
              definitionDependencies_toDefinitionId: definitionDependents,
              ...rest
            } = def;

            return {
              ...rest,
              definitionDependencies,
              definitionDependents,
            };
          });
        } finally {
          close();
        }
      }),

    byId: publicProcedure
      .input(definitionByIdSchema)
      .query(async ({ input }) => {
        const { id, projectSlug } = input;

        const { dbUrl } = await getProjectDbConfig(projectSlug);

        if (!dbUrl) {
          throw new Error("Project database configuration not found");
        }

        const { tursoDb: db, close } = getAnalysisDB(dbUrl);

        try {
          // Use Drizzle's relations to efficiently fetch definition with all related data
          const definition = await db.query.definitions.findFirst({
            where: eq(definitions.id, id),
            with: {
              file: {
                columns: {
                  id: true,
                  filePath: true, // keep it small
                  language: true,
                },
              },
              references_sourceDefinitionId: true,
              definitionDependencies_fromDefinitionId: {
                with: {
                  definition_toDefinitionId: true,
                },
              },
              definitionDependencies_toDefinitionId: {
                with: {
                  definition_fromDefinitionId: true,
                },
              },
            },
          });

          if (!definition) {
            throw new Error("Definition not found");
          }

          const {
            references_sourceDefinitionId: references,
            definitionDependencies_fromDefinitionId: definitionDependencies,
            definitionDependencies_toDefinitionId: definitionDependents,
            ...rest
          } = definition;

          // Transform to match the expected API structure
          return {
            ...rest,
            references,
            definitionDependencies,
            definitionDependents,
          };
        } finally {
          close();
        }
      }),
  }),

  // Packages endpoints
  packages: router({
    withReadme: publicProcedure
      .input(projectIdSchema)
      .query(async ({ input }) => {
        const { projectSlug } = input;

        const { dbUrl } = await getProjectDbConfig(projectSlug);

        if (!dbUrl) {
          throw new Error("Project database configuration not found");
        }

        const { tursoDb: db, close } = getAnalysisDB(dbUrl);

        try {
          return await db
            .select({
              id: packages.id,
              name: packages.name,
              path: packages.path,
              entry_point: packages.entryPoint,
              workspace_type: packages.workspaceType,
              is_workspace_root: packages.isWorkspaceRoot,
              created_at: packages.createdAt,
              updated_at: packages.updatedAt,
              readme_content: packages.readmeContent,
            })
            .from(packages);
        } finally {
          close();
        }
      }),
  }),

  // Health check
  health: publicProcedure.query(async () => {
    return {
      status: "healthy",
      database: "sqlite",
      mode: "read-only",
    };
  }),
});
