"use client";

import { useDefinition, useFile } from "@/hooks/useApi";
import { CitationProperties } from "@/lib/utils/remarkCitations";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";

function clamp(text: string, max = 280) {
  if (!text) return "";
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "\u2026";
}

function extractGist(xmlLike: string | undefined | null): string | null {
  if (!xmlLike) return null;
  const m = xmlLike.match(/<gist>([\s\S]*?)<\/gist>/i);
  if (!m) return null;
  return m[1].trim();
}

function stripTags(s: string): string {
  return s.replace(/<[^>]*>/g, "");
}

export function CitationPreview({
  citation,
  open,
  anchor,
}: {
  citation: CitationProperties;
  open: boolean;
  anchor: HTMLElement | null;
}) {
  const isDefinition =
    citation.citationType === "definition" && !!citation.definitionId;

  // Fetch definition or file details
  const defId = isDefinition ? Number(citation.definitionId) : undefined;
  const fileId = Number(citation.fileId);

  const { data: defData } = useDefinition(defId as number);
  const { data: fileData } = useFile(fileId);

  // Prefer definition for summary when present
  const summary = useMemo(() => {
    // Use aiShortSummary only. If absent, render explicit fallback.
    if (isDefinition && defData) {
      const short = defData?.aiShortSummary?.trim?.();
      return short ? clamp(stripTags(short)) : "";
    }
    if (!isDefinition && fileData) {
      const short = fileData?.aiShortSummary?.trim?.();
      return short ? clamp(stripTags(short)) : "";
    }
    return "";
  }, [defData, fileData, isDefinition]);

  const title = useMemo(() => {
    if (isDefinition && defData) {
      return `${defData.name} ${defData.definitionType ? `· ${defData.definitionType}` : ""}`;
    }
    if (fileData) {
      const parts = fileData.filePath.split("/");
      return parts[parts.length - 1] || fileData.filePath;
    }
    return citation.text;
  }, [defData, fileData, isDefinition, citation.text]);

  const subtitle = useMemo(() => {
    if (isDefinition && defData) {
      return `${defData.file.filePath}${defData.startLine ? `:${defData.startLine}-${defData.endLine}` : ""}`;
    }
    if (fileData) return fileData.filePath;
    return "";
  }, [defData, fileData, isDefinition]);

  // Positioning state (viewport-fixed)
  const [pos, setPos] = useState<{ top: number; left: number }>({
    top: -9999,
    left: -9999,
  });

  const cardRef = useRef<HTMLDivElement | null>(null);

  const recompute = () => {
    const margin = 8;
    const maxWidth = 360;
    const anchorRect = anchor?.getBoundingClientRect();
    if (!anchorRect) return;

    // Provisional size; measure if available
    const cardRect = cardRef.current?.getBoundingClientRect();
    const cw = Math.min(cardRect?.width || maxWidth, maxWidth);
    const ch = cardRect?.height || 120;

    // Prefer below; flip above if needed
    const spaceBelow = window.innerHeight - anchorRect.bottom;
    const placeBelow = spaceBelow >= ch + margin;
    const top = placeBelow
      ? anchorRect.bottom + margin
      : Math.max(margin, anchorRect.top - ch - margin);

    // Clamp horizontally to viewport
    const idealLeft = anchorRect.left; // align start
    const left = Math.min(
      Math.max(margin, idealLeft),
      window.innerWidth - cw - margin,
    );
    setPos({ top: Math.round(top), left: Math.round(left) });
  };

  useLayoutEffect(() => {
    if (!open) return;
    recompute();
    // Recompute after content renders
    const t = setTimeout(recompute, 0);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, summary, anchor]);

  useEffect(() => {
    if (!open) return;
    const onResize = () => recompute();
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, true);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onResize, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Simple mount/unmount animation timing
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => setVisible(true), 120);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setVisible(false), 120);
    return () => clearTimeout(t);
  }, [open]);

  if (!open && !visible) return null;

  const content = (
    <div
      ref={cardRef}
      className={`pointer-events-none fixed z-[60] w-[360px] max-w-[calc(100vw-16px)] rounded-md border border-border bg-card shadow-lg ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-1"
      } transition-all duration-150`}
      role="tooltip"
      style={{ top: pos.top, left: pos.left }}
    >
      <div className="p-3">
        <div className="text-sm font-medium text-foreground truncate">
          {title}
        </div>
        {subtitle && (
          <div className="text-[11px] text-muted-foreground truncate mt-0.5">
            {subtitle}
          </div>
        )}
        <div className="mt-2 text-xs text-foreground/90 prose prose-xs dark:prose-invert max-w-none">
          {summary ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw, rehypeSanitize]}
            >
              {summary}
            </ReactMarkdown>
          ) : (
            <span>No summary available.</span>
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
