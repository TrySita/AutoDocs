"use client";

import { DefinitionResponse } from "@/types/codebase";
import { Editor, OnMount } from "@monaco-editor/react";
import { useLayoutEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

export const SideBySideView = ({
  def,
  theme = "light",
  definitionCode,
}: {
  def: DefinitionResponse;
  theme?: string;
  definitionCode: string;
}) => {
  const docRef = useRef<HTMLDivElement>(null);
  const monacoRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [docH, setDocH] = useState<number>(0);

  /* ─────────────────────────────────  Measure the doc pane ── */
  useLayoutEffect(() => {
    if (!docRef.current) return;

    const update = () => {
      const h = docRef.current!.getBoundingClientRect().height;
      setDocH(Math.max(h, 600));
      // after the state updates, Monaco gets a new height prop, so re-layout:
      monacoRef.current?.layout();
    };

    const ro = new ResizeObserver(update);
    ro.observe(docRef.current);
    window.addEventListener("resize", update);

    update(); // first paint
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  /* ────────────────────────────────────────────────  UI ── */
  return (
    <div className="grid grid-cols-2">
      {/* ── Source code ─────────────────────────────── */}
      <div className="border-r">
        <Editor
          onMount={(editor, monaco) => {
            monacoRef.current = editor;
            ["typescript", "javascript"].forEach((lang) => {
              (
                monaco.languages.typescript[
                  `${lang}Defaults` as keyof typeof monaco.languages.typescript
                ] as typeof monaco.languages.typescript.typescriptDefaults
              ).setDiagnosticsOptions({
                diagnosticCodesToIgnore: [7027, 6133], // unreachable, unused
              });
            });
          }}
          height={docH ? `${docH}px` : "auto"} // <- match doc height
          language="typescript"
          value={definitionCode}
          theme={theme === "dark" ? "vs-dark" : "light"}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            scrollbar: { vertical: "auto", horizontal: "auto" },
            fontSize: 13,
            lineNumbers: "on",
            renderWhitespace: "selection",
            wordWrap: "on",
            contextmenu: false,
            folding: false,
            lineNumbersMinChars: 3,
          }}
        />
      </div>

      {/* ── Documentation ───────────────────────────── */}
      <div className="px-4 bg-muted/10 overflow-auto" ref={docRef}>
        {def.docstring && (
          <>
            <h4 className="font-medium text-sm text-muted-foreground mb-2">
              Docstring
            </h4>
            <div className="text-sm whitespace-pre-wrap text-foreground">
              {def.docstring}
            </div>
          </>
        )}

        {def.aiSummary && (
          <div className="markdown mt-0 pt-0">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={[rehypeRaw, rehypeSanitize]}
            >
              {def.aiSummary}
            </ReactMarkdown>
          </div>
        )}

        {/* metadata … */}
      </div>
    </div>
  );
};
