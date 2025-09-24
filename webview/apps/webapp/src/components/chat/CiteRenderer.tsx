"use client";

import type { Components as MDComponents } from "react-markdown";
import { z } from "zod";
import { CitationLink } from "./CitationLink";
import type { CitationProperties } from "@/lib/utils/remarkCitations";

const citationSchema: z.ZodType<CitationProperties> = z.object({
  text: z.string(),
  citationType: z.enum(["file", "definition"]),
  fileId: z.string(),
  definitionId: z.string().optional(),
});

export const mdCiteRenderer: NonNullable<MDComponents["cite"]> = (props) => {
  const result = citationSchema.safeParse(props);
  if (!result.success) {
    return <span>{props.children}</span>;
  }
  return <CitationLink citation={result.data} />;
};

