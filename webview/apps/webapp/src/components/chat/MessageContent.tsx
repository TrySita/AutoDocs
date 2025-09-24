"use client";

import remarkCitations from "@/lib/utils/remarkCitations";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { mdCiteRenderer } from "./CiteRenderer";

interface MessageContentProps {
  content: string;
  className?: string;
}

export function MessageContent({
  content,
  className = "",
}: MessageContentProps) {
  const components = { cite: mdCiteRenderer };
  return (
    <div
      className={`prose prose-sm max-w-full dark:prose-invert ${className} break-words`}
    >
      <div className="markdown">
        <ReactMarkdown
          remarkPlugins={[remarkCitations, remarkGfm, remarkMath]}
          rehypePlugins={[rehypeHighlight]}
          components={components}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
