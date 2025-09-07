"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function UserWorkspacePage() {
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    // Redirect to docs route by default
    const repoId = params.repoId as string;
    router.replace(`/workspace/${repoId}/docs`);
  }, [router, params.repoId]);

  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Redirecting...</p>
      </div>
    </div>
  );
}
