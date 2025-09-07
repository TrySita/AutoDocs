"use client";

import { LoadingAnimation } from "@/components/common/framer-animation/loading-animation";
import UserWorkspace from "@/pageComponents/UserWorkspace";
import { Suspense } from "react";

export default function SourcePage() {
  return (
    <Suspense fallback={<LoadingAnimation size="sm" />}>
      <UserWorkspace view="source" />
    </Suspense>
  );
}
