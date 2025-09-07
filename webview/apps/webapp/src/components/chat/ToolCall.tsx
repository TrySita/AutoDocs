import { ToolCall as ToolCallType } from "@/types/chat";
import { isDev } from "@/utils/getStage";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { useEffect, useState } from "react";

interface ToolCallProps {
  toolCall: ToolCallType;
}

export function ToolCall({ toolCall }: ToolCallProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Auto-expand when streaming or executing
  useEffect(() => {
    if (toolCall.status === "streaming" || toolCall.status === "executing") {
      setIsExpanded(true);
    }
  }, [toolCall.status]);

  const getStatusText = () => {
    switch (toolCall.status) {
      case "pending":
        return "Preparing search...";
      case "streaming":
        return "Generating search parameters...";
      case "executing":
        return "Searching...";
      case "completed":
        const searchCount = toolCall.arguments?.searches?.length ?? 0;
        return `Found results for ${searchCount} search${searchCount > 1 ? "es" : ""}`;
      case "failed":
        return "Search failed";
    }
  };

  return (
    <div className="rounded-lg p-4 bg-muted/30">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <Search className="w-5 h-5 text-blue-500" />
          <div>
            <div className="font-medium">Codebase Search</div>
          </div>
        </div>
      </div>

      <AnimatePresence>
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="overflow-hidden"
        >
          <div className="mt-4 space-y-4">
            {/* Streaming Arguments */}
            {toolCall.status === "streaming" && toolCall.argumentsText && (
              <div>
                <h4 className="text-sm font-medium mb-2">
                  Generating Search Parameters:
                </h4>
                <div className="bg-background/50 rounded-md p-3 border">
                  <div className="font-mono text-sm text-muted-foreground">
                    {toolCall.argumentsText}
                    <span className="animate-pulse">|</span>
                  </div>
                </div>
              </div>
            )}

            {/* Search Queries */}
            {(toolCall.arguments?.searches?.length ?? 0) > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">Search Queries:</h4>
                <div className="space-y-2">
                  {(toolCall.arguments?.searches ?? []).map((search, index) => (
                    <div
                      key={index}
                      className="bg-background/50 rounded-md p-3 border"
                    >
                      <div className="font-mono text-sm">
                        &ldquo;{search.query}&rdquo;
                      </div>
                      {isDev() && (
                        <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                          <span>Limit: {search.limit || 5}</span>
                          <span>
                            Threshold: {search.similarity_threshold || 0.1}
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Results */}
            {toolCall.status === "completed" && toolCall.results && (
              <div>
                <h4 className="text-sm font-medium mb-2">Results:</h4>
                <div className="space-y-3">
                  {toolCall.results.map((result, index) => (
                    <div key={index} className="border rounded-md">
                      <div className="bg-muted/50 px-3 py-2 border-b">
                        <div className="text-sm font-medium">
                          Query {index + 1}: &ldquo;{result.query}&rdquo;
                        </div>
                      </div>
                      <div className="p-3">
                        <div className="text-sm whitespace-pre-wrap font-mono">
                          {result.result.substring(0, 500)}...{" "}
                          {result.result.length > 500 && (
                            <span className="text-xs text-muted-foreground">
                              (truncated)
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error message */}
            {toolCall.status === "failed" && (
              <div className="bg-red-50 border border-red-200 rounded-md p-3">
                <div className="text-sm text-red-800">
                  Search execution failed. Please try again.
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
