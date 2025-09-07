"use client";

import { currentRepoSlugAtom } from "@/lib/atoms/workspace";
import { useSetAtom } from "jotai";
import { useParams } from "next/navigation";
import { useEffect } from "react";

interface WorkspaceLayoutProps {
  children: React.ReactNode;
}

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  const params = useParams();
  const setCurrentRepoSlug = useSetAtom(currentRepoSlugAtom);

  useEffect(() => {
    if (params.repoId && typeof params.repoId === "string") {
      setCurrentRepoSlug(params.repoId);
    }
  }, [params.repoId, setCurrentRepoSlug]);

  return <>{children}</>;
}
