"use client";

import { currentRepoSlugAtom } from "@/lib/atoms/workspace";
import { useTRPC } from "@/lib/trpc/client";
import { useQuery } from "@tanstack/react-query";
import { TRPCClientError } from "@trpc/client";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import type { components } from "@/types/api";

type APIJobStatus = components["schemas"]["JobStatusResponse"]["status"];
type APIJobProgress = components["schemas"]["JobStatusResponse"]["progress"];

// True when the job-status query failed because the API reported the job as
// unknown (404 -> tRPC NOT_FOUND). The in-memory job queue loses jobs across
// API restarts, so a previously-enqueued job can vanish; callers must treat
// this as terminal and not keep polling a job that will never come back.
export const isJobNotFoundError = (error: unknown): boolean =>
  error instanceof TRPCClientError && error.data?.code === "NOT_FOUND";

export const JOB_PROGRESS_ORDER: readonly APIJobProgress[] = [
  "queued",
  "starting",
  "cloning_repo",
  "parse",
  "summaries",
  "embeddings",
  "finalize",
  "completed",
  "failed",
] as const;

export const isBusyStatus = (s: APIJobStatus | undefined) =>
  s === "queued" || s === "running";
export const isTerminalStatus = (s: APIJobStatus | undefined) =>
  s === "succeeded" || s === "failed";

export const useIngestionStatus = (
  jobId: string | undefined,
  opts?: { intervalMs?: number }
) => {
  const trpc = useTRPC();
  const enabled = Boolean(jobId);
  const interval = opts?.intervalMs ?? 2500;

  const query = useQuery({
    ...trpc.ingestion.jobStatus.queryOptions({ jobId: jobId! }),
    enabled,
    // A NOT_FOUND job is gone for good; don't retry it and stop the poll loop so
    // we don't hammer the API with a 404 every interval forever.
    retry: (_failureCount, error) => !isJobNotFoundError(error),
    refetchInterval: (q) =>
      enabled && !isJobNotFoundError(q.state.error) ? interval : false,
  });

  const jobLost = isJobNotFoundError(query.error);

  const phaseInfo = useMemo(() => {
    const progress = (query.data?.progress || "queued") as APIJobProgress;
    const idx = Math.max(0, JOB_PROGRESS_ORDER.indexOf(progress));
    const total = JOB_PROGRESS_ORDER.length - 1; // treat failed/completed as end
    const pct = Math.min(100, Math.round((idx / total) * 100));
    return { progressText: progress, percent: pct };
  }, [query.data?.progress]);

  return { ...query, jobId, jobLost, ...phaseInfo };
};

export const useFiles = (params?: {
  limit?: number;
  offset?: number;
  language?: string;
}) => {
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);

  return useQuery({
    ...trpc.analysis.files.list.queryOptions({
      projectSlug: projectSlug!,
      ...params,
    }),
    enabled: !!projectSlug,
  });
};

export const useFile = (fileId: number) => {
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);

  return useQuery({
    ...trpc.analysis.files.byId.queryOptions({
      id: fileId,
      projectSlug: projectSlug!,
    }),
    enabled: !!fileId && !!projectSlug,
  });
};

export const useDefinitions = (definitionIds: number[]) => {
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);

  // Use the efficient batch endpoint
  return useQuery({
    ...trpc.analysis.definitions.batch.queryOptions({
      ids: definitionIds,
      projectSlug: projectSlug!,
    }),
    enabled: definitionIds.length > 0 && !!projectSlug,
  });
};

export const useDefinition = (definitionId: number) => {
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);

  return useQuery({
    ...trpc.analysis.definitions.byId.queryOptions({
      id: definitionId,
      projectSlug: projectSlug!,
    }),
    enabled: !!definitionId && !!projectSlug,
  });
};

export const usePackagesWithReadme = () => {
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);

  return useQuery({
    ...trpc.analysis.packages.withReadme.queryOptions({
      projectSlug: projectSlug!,
    }),
    enabled: !!projectSlug,
  });
};

export const useHealth = () => {
  const trpc = useTRPC();
  return useQuery(trpc.analysis.health.queryOptions());
};
