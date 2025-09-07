"use client";

import UserWorkspace from "@/pageComponents/UserWorkspace";
import { Suspense } from "react";
export default function DocsPage() {
  return (
    <Suspense>
      <UserWorkspace view="docs" />
    </Suspense>
  );
}
