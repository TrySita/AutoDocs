/* eslint-disable @next/next/no-img-element */
"use client";

import { Card, CardContent } from "@/components/common/shadcn-components/card";
import { Button } from "@/components/common/shadcn-components/button";
import { Input } from "@/components/common/shadcn-components/input";
import { usePublicProjects } from "@/hooks/usePublicProjects";
import { motion } from "framer-motion";
import { Copy, Search, X, ExternalLink, RotateCw } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/common/shadcn-components/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/common/shadcn-components/dialog";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useTRPC } from "@/lib/trpc/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useIngestionStatus, isBusyStatus } from "@/hooks/useApi";
import { AppRouter } from "@/lib/trpc/router";
import { inferRouterInputs } from "@trpc/server";
import { components } from "@/types/api";

export default function CodebasesPage() {
  const router = useRouter();
  const { publicProjects, isLoading } = usePublicProjects(100);
  const [search, setSearch] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const trpc = useTRPC();
  const queryClient = useQueryClient();

  const listQueryKey = trpc.projects.getPublicProjects.queryOptions({
    limit: 100,
  }).queryKey;

  const { mutateAsync: deleteProject } = useMutation(
    trpc.projects.deletePublicProject.mutationOptions({
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: listQueryKey });
      },
    })
  );

  const { mutateAsync: addProject } = useMutation(
    trpc.projects.addPublicProject.mutationOptions({
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: listQueryKey });
      },
    })
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return publicProjects || [];
    return (
      publicProjects?.filter((p) =>
        [p.name, p.slug, p.description]
          .filter(Boolean)
          .some((s) => String(s).toLowerCase().includes(q))
      ) || []
    );
  }, [publicProjects, search]);

  const handleOSSProject = (projectSlug: string) => {
    router.push(`/workspace/${projectSlug}`);
  };

  return (
    <div className="container max-w-6xl mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6 gap-4">
        <h1 className="text-3xl font-bold">Repositories</h1>
        <div className="flex items-center gap-3">
          <div className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search repositories"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
          {/* Add New modal trigger */}
          <AddProjectDialog onAdd={addProject} />
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.7 }}
        className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 lg:gap-8 max-w-full mx-auto"
      >
        {isLoading
          ? // Loading skeleton
            Array.from({ length: 5 }).map((_, index) => (
              <Card key={index} className="bg-card/50 backdrop-blur-sm h-full">
                <CardContent className="flex flex-col items-center justify-center p-3 sm:p-6 lg:p-8 h-full min-h-[120px] sm:min-h-[150px]">
                  <div className="h-10 w-10 sm:h-16 sm:w-16 lg:h-20 lg:w-20 bg-muted rounded-lg animate-pulse flex-shrink-0" />
                  <div className="mt-2 sm:mt-4 lg:mt-6 h-3 sm:h-5 lg:h-6 w-16 sm:w-20 lg:w-24 bg-muted rounded animate-pulse" />
                </CardContent>
              </Card>
            ))
          : filtered.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onDelete={async () => {
                  deleteProject({ id: project.id });
                }}
                onOpen={(slug) => handleOSSProject(slug)}
                copiedId={copiedId}
                setCopiedId={setCopiedId}
              />
            ))}
      </motion.div>

      {/* Removed floating Add New; using header dialog trigger */}
    </div>
  );
}

function AddProjectDialog({
  onAdd,
}: {
  onAdd: (
    input: inferRouterInputs<AppRouter>["projects"]["addPublicProject"]
  ) => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [saving, setSaving] = useState(false);

  // derive slug from name: lowercase, spaces -> hyphens, remove invalid chars
  const derivedSlug = name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-_]/g, "");
  const slugValid = derivedSlug.length > 0 && /^[a-z0-9-_]+$/.test(derivedSlug);
  const canSave =
    name.trim().length > 0 &&
    repositoryUrl.trim().length > 0 &&
    slugValid &&
    !saving;

  const submit = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      await onAdd({
        repositoryUrl: repositoryUrl.trim(),
        slug: derivedSlug,
        name: name.trim(),
        autoStart: true,
      });
      setOpen(false);
      setName("");
      setRepositoryUrl("");
    } catch (e) {
      console.error("Add project failed", e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button onClick={() => setOpen(true)}>Add New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add New Repository</DialogTitle>
          <DialogDescription>
            Provide the repository name and URL. The repo ID is derived from the
            name (lowercase, spaces replaced with hyphens).
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1">
            <label className="text-sm">Repository Name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Excalidraw"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm">Repository URL</label>
            <Input
              value={repositoryUrl}
              onChange={(e) => setRepositoryUrl(e.target.value)}
              placeholder="https://github.com/org/repo"
            />
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Slug: <span className="font-mono">{derivedSlug || "—"}</span>
          </p>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => setOpen(false)}
            disabled={saving}
          >
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSave}>
            {saving ? "Adding…" : "Add"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProjectCard({
  project,
  onOpen,
  onDelete,
  copiedId,
  setCopiedId,
}: {
  project: {
    id: string;
    name: string;
    slug: string;
    repositoryUrl: string | null;
    latestJobId?: string | null;
    latestJobStatus?: string | null;
  };
  onOpen: (slug: string) => void;
  onDelete: () => Promise<void>;
  copiedId: string | null;
  setCopiedId: (id: string | null) => void;
}) {
  const trpc = useTRPC();
  const queryClient = useQueryClient();
  const listQueryKey = trpc.projects.getPublicProjects.queryOptions({
    limit: 100,
  }).queryKey;
  const {
    data: job,
    percent,
    progressText,
  } = useIngestionStatus(project.latestJobId || undefined);
  const status = (job?.status ?? project.latestJobStatus) as
    | components["schemas"]["JobStatusResponse"]["status"]
    | undefined;
  const isBusy = isBusyStatus(status);
  const hasFailed = job?.status === "failed";
  const hasSucceeded = job?.status === "succeeded";
  const canReingest = !isBusy; // allow reingest on idle states
  const { mutateAsync: reingest } = useMutation(
    trpc.projects.reingestPublicProject.mutationOptions({
      onSuccess: () =>
        queryClient.invalidateQueries({ queryKey: listQueryKey }),
    })
  );

  return (
    <div key={project.id}>
      <Card
        className={`relative border bg-card transition-colors h-full ${
          isBusy
            ? "opacity-90"
            : "hover:bg-muted/50 hover:border-muted-foreground/20"
        }`}
      >
        {/* Header row */}
        <div className="flex items-start justify-between p-4 pb-2">
          <div
            className={`min-w-0 ${!isBusy ? "cursor-pointer" : ""}`}
            onClick={() => {
              if (!isBusy) onOpen(project.slug);
            }}
          >
            <div className="text-base sm:text-lg font-semibold text-foreground truncate">
              {project.name}
            </div>
            <div className="mt-1 text-xs text-muted-foreground truncate flex items-center gap-1">
              {project.repositoryUrl ? (
                <a
                  href={project.repositoryUrl}
                  onClick={(e) => e.stopPropagation()}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 hover:underline"
                  title={project.repositoryUrl}
                >
                  Repo Link <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span>No repo URL</span>
              )}
            </div>
          </div>

          {/* Delete button with confirm */}
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="shrink-0"
                title="Delete"
                onClick={(e) => e.stopPropagation()}
                disabled={isBusy}
              >
                <X className="w-4 h-4" />
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent onClick={(e) => e.stopPropagation()}>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete repository?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will remove the repo “{project.name}” from your
                  Repositories list, as well as any generated docs, embeddings,
                  and conversations. This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel onClick={(e) => e.stopPropagation()}>
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction
                  onClick={async (e) => {
                    e.stopPropagation();
                    try {
                      await onDelete();
                    } catch (err) {
                      console.error("Failed to delete project", err);
                    }
                  }}
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>

        {/* Body */}
        <CardContent className="pt-0 px-4 pb-4">
          {isBusy && (
            <div className="mt-2">
              <div className="h-1.5 w-full bg-muted rounded">
                <div
                  className="h-1.5 bg-primary rounded"
                  style={{ width: `${percent}%`, transition: "width 300ms" }}
                />
              </div>
              <div className="mt-1 text-[10px] text-muted-foreground uppercase tracking-wide">
                {progressText || "starting"} · {percent}%
              </div>
            </div>
          )}

          {hasFailed && (
            <div className="mt-3 text-[11px] inline-flex items-center gap-2 text-red-500">
              <span className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 rounded">
                Ingest failed
              </span>
              {job?.error && (
                <span
                  className="text-muted-foreground truncate"
                  title={job.error}
                >
                  {String(job.error).slice(0, 80)}
                  {job.error.length > 80 ? "…" : ""}
                </span>
              )}
            </div>
          )}

          {/* Footer actions */}
          <div className="mt-4 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              {/* <Button
                size="sm"
                onClick={async (e) => {
                  e.stopPropagation();
                  try {
                    await reingest({ id: project.id });
                  } catch (err) {
                    console.error("Failed to reingest", err);
                  }
                }}
                disabled={!canReingest}
                title="Reingest repository"
              >
                <RotateCw className="w-4 h-4 mr-1" />
                {isBusy ? "Ingesting…" : "Sync"}
              </Button> */}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                navigator.clipboard
                  .writeText(project.slug)
                  .then(() => {
                    setCopiedId(project.slug);
                    setTimeout(() => setCopiedId(null), 1500);
                  })
                  .catch((err) => console.error("Clipboard write failed", err));
              }}
              disabled={isBusy}
              title="Copy repo ID"
            >
              <Copy className="w-4 h-4 mr-1" />
              {copiedId === project.slug ? "Copied!" : "Copy ID"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
