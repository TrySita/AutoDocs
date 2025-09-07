import { publicProjects, supabaseDb } from "@sita/shared";
import { eq } from "drizzle-orm";
import { z } from "zod";
import { publicProcedure, router } from "../init";

export const projectRouter = router({
  getPublicProjects: publicProcedure
    .input(
      z
        .object({
          limit: z.number().optional().default(5),
        })
        .optional(),
    )
    .query(async ({ input }) => {
      const limit = input?.limit || 5;

      try {
        const data = await supabaseDb.query.publicProjects.findMany({
          where: eq(publicProjects.isActive, true),
          orderBy: publicProjects.sortOrder,
          limit: limit,
        });

        return data || [];
      } catch (e) {
        console.error("Failed to fetch public projects:", e);
        throw new Error("Failed to fetch public projects");
      }
    }),

  deletePublicProject: publicProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => {
      // Load the project to obtain slug for cleanup
      const proj = await supabaseDb.query.publicProjects.findFirst({
        where: eq(publicProjects.id, input.id),
      });

      // Attempt to delete local analysis artifacts (DB + clone) on the ingestion API
      try {
        if (proj) {
          const baseUrl = process.env.INGESTION_API_URL;
          if (!baseUrl)
            throw new Error("INGESTION_API_URL not set");
          const res = await fetch(`${baseUrl}/repo/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ repo_slug: proj.slug }),
          });
          if (!res.ok) {
            const text = await res.text();
            console.error(`Delete repo failed: ${res.status} ${text}`);
          }
        }
      } catch (e) {
        // Swallow cleanup errors; still remove the project record
        console.error("Failed to request repo deletion:", e);
      }

      await supabaseDb
        .delete(publicProjects)
        .where(eq(publicProjects.id, input.id));
      return { success: true } as const;
    }),

  addPublicProject: publicProcedure
    .input(
      z.object({
        repositoryUrl: z.string().url(),
        slug: z
          .string()
          .trim()
          .transform((s) => s.toLowerCase())
          .refine((s) => /^[a-z0-9-_]+$/.test(s), {
            message: "Repo ID must be lowercase letters and digits only",
          }),
        // Optional explicit fields (fallbacks derived from URL if not provided)
        name: z.string().optional(),
        // When true, kick off ingestion immediately on server
        autoStart: z.boolean().optional().default(true),
      }),
    )
    .mutation(async ({ input }) => {
      // Derive name from repo URL if not provided; slug comes from validated input
      let derivedName = input.name;

      if (!derivedName) {
        try {
          const u = new URL(input.repositoryUrl);
          const parts = u.pathname.split("/").filter(Boolean);
          const repoName =
            parts[parts.length - 1] || u.hostname.replace(/^www\./, "");
          derivedName = repoName;
        } catch {
          // Fallback if URL parsing fails
          const cleaned =
            input.repositoryUrl
              .toLowerCase()
              .replace(/[^a-z0-9-]+/g, "-")
              .replace(/^-+|-+$/g, "")
              .slice(-40) || "repo";
          derivedName = cleaned;
        }
      }

      const [created] = await supabaseDb
        .insert(publicProjects)
        .values({
          name: derivedName,
          slug: input.slug,
          repositoryUrl: input.repositoryUrl,
          isActive: true,
        })
        .returning();
      // Optionally start ingestion on server and persist job id/status
      try {
        if (input.autoStart) {
          const baseUrl = process.env.INGESTION_API_URL;
          if (!baseUrl)
            throw new Error("INGESTION_API_URL not set");

          const res = await fetch(`${baseUrl}/ingest/github`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              github_url: input.repositoryUrl,
              repo_slug: input.slug,
              db_path: `${input.slug}.db`,
              branch: null,
              force_full: false,
            }),
          });
          if (!res.ok) {
            const text = await res.text();
            throw new Error(`Ingestion enqueue failed: ${res.status} ${text}`);
          }
          const data = (await res.json()) as { job_id: string; status: string };
          const [updated] = await supabaseDb
            .update(publicProjects)
            .set({ latestJobId: data.job_id, latestJobStatus: data.status })
            .where(eq(publicProjects.id, created.id))
            .returning();
          return updated;
        }
      } catch (err) {
        // swallow server-side ingestion errors; project record already exists
        console.error("Server-side ingestion start failed:", err);
      }
      return created;
    }),
  reingestPublicProject: publicProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input }) => {
      // Load project
      const proj = await supabaseDb.query.publicProjects.findFirst({
        where: eq(publicProjects.id, input.id),
      });
      if (!proj) throw new Error("Project not found");
      const baseUrl = process.env.INGESTION_API_URL;
      if (!baseUrl) throw new Error("INGESTION_API_URL not set");

      const res = await fetch(`${baseUrl}/ingest/github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          github_url: proj.repositoryUrl,
          repo_slug: proj.slug,
          db_path: `${proj.slug}.db`,
          branch: null,
          force_full: false,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Ingestion enqueue failed: ${res.status} ${text}`);
      }
      const data = (await res.json()) as { job_id: string; status: string };
      const [updated] = await supabaseDb
        .update(publicProjects)
        .set({ latestJobId: data.job_id, latestJobStatus: data.status })
        .where(eq(publicProjects.id, input.id))
        .returning();
      return updated;
    }),
});
