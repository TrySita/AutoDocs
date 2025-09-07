"use client";

import remarkCitations, {
  CitationProperties,
} from "@/lib/utils/remarkCitations";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CitationLink } from "./CitationLink";

interface MessageContentProps {
  content: string;
  className?: string;
}

export function MessageContent({
  content,
  className = "",
}: MessageContentProps) {
  return (
    <div
      className={`prose prose-sm max-w-full dark:prose-invert ${className} break-words`}
    >
      <div className="markdown">
        <ReactMarkdown
          remarkPlugins={[remarkCitations, remarkGfm, remarkMath]}
          rehypePlugins={[rehypeHighlight]}
          components={{
            // Handle custom citation nodes created by our remark plugin
            // @ts-expect-error: ReactMarkdown doesn't recognize custom components
            citation: (citation: CitationProperties) => {
              return <CitationLink citation={citation} />;
              // return ;
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}
