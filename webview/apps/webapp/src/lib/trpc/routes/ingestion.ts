import { publicProcedure, router } from "../init";
import { z } from "zod";
import type { components } from "@/types/api";

type JobStatusResponse = components["schemas"]["JobStatusResponse"];

export const ingestionRouter = router({
  jobStatus: publicProcedure
    .input(
      z.object({
        jobId: z.string().min(1),
      }),
    )
    .query(async ({ input }) => {
      const baseUrl = process.env.INGESTION_API_URL;
      if (!baseUrl) throw new Error("INGESTION_API_URL not set");

      const res = await fetch(`${baseUrl}/ingest/jobs/${input.jobId}`);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Failed to fetch job status: ${res.status} ${text}`);
      }
      return (await res.json()) as JobStatusResponse;
    }),
});

