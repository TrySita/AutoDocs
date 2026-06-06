import { publicProcedure, router } from "../init";
import { TRPCError } from "@trpc/server";
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
        // A 404 means the job is unknown to the API: either a bogus id or a job
        // lost to an API restart (the queue is in-memory). Surface it as a typed
        // NOT_FOUND so the poller can stop and the UI can render a non-busy
        // "lost" state instead of retrying a permanently-missing job forever.
        if (res.status === 404) {
          throw new TRPCError({
            code: "NOT_FOUND",
            message: `Ingestion job not found: ${input.jobId}`,
          });
        }
        throw new Error(`Failed to fetch job status: ${res.status} ${text}`);
      }
      return (await res.json()) as JobStatusResponse;
    }),
});

