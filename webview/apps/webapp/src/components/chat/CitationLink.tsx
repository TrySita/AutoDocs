import { currentRepoSlugAtom } from "@/lib/atoms/workspace";
import { CitationProperties } from "@/lib/utils/remarkCitations";
import { useAtomValue } from "jotai";
import Link from "next/link";
import { useRef, useState } from "react";
import { CitationPreview } from "./CitationPreview";

interface CitationLinkProps {
  citation: CitationProperties;
}

export function CitationLink({ citation }: CitationLinkProps) {
  const isFile = citation.citationType === "file";

  const repoId = useAtomValue(currentRepoSlugAtom);

  // Generate the appropriate URL based on citation type
  const href = isFile
    ? `/workspace/${repoId}/docs?fileId=${citation.fileId}`
    : `/workspace/${repoId}/docs?fileId=${citation.fileId}&definitionId=${citation.definitionId}`;

  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLSpanElement | null>(null);

  return (
    <span className="relative inline-block" ref={anchorRef}>
      <Link
        href={href}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className={`inline-flex items-center px-2 font-medium rounded-md border transition-colors hover:opacity-80 
        ${isFile ? "border-blue-700" : "border-purple-700"}
      `}
      >
        {citation.text}
      </Link>
      <CitationPreview
        citation={citation}
        open={open}
        anchor={anchorRef.current}
      />
    </span>
  );
}
