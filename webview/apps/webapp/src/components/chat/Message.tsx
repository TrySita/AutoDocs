import { Button } from "@/components/common/shadcn-components/button";
import { Message as MessageType } from "@/types/chat";
import { motion } from "framer-motion";
import { Brain, Check, Copy } from "lucide-react";
import { useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../common/shadcn-components/accordion";
import { AgentTurns } from "./AgentTurns";
import { MessageContent } from "./MessageContent";

function LoadingDots() {
  return (
    <div className="flex space-x-2">
      <motion.div
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.5, repeat: Infinity }}
        className="w-2 h-2 bg-current rounded-full"
      />
      <motion.div
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
        className="w-2 h-2 bg-current rounded-full"
      />
      <motion.div
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.5, repeat: Infinity, delay: 0.4 }}
        className="w-2 h-2 bg-current rounded-full"
      />
    </div>
  );
}

export function Message({
  role,
  content,
  timestamp,
  isStreaming,
  reasoning,
  agentTurns,
  isAgentComplete,
  isReasoningComplete,
}: MessageType) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy text: ", err);
    }
  };

  const hasReasoning = !!reasoning;
  const hasAgentActivity = (agentTurns?.length ?? 0) > 0;

  // "Thinking…" is true only until you mark reasoning complete
  const isReasoningInProgress =
    hasReasoning && isStreaming && !isReasoningComplete;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex ${role === "user" ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[90%] rounded-lg p-4 relative group ${
          role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
        }`}
      >
        {hasReasoning && (
          <Accordion
            type="single"
            collapsible
            defaultValue="reasoning"
            className="mb-4 border border-border rounded-lg px-3 bg-background/50"
          >
            <AccordionItem value="reasoning">
              <AccordionTrigger className="w-full">
                <div className="flex items-center gap-2">
                  <Brain
                    className={`h-4 w-4 text-foreground ${isReasoningInProgress ? "animate-pulse" : ""}`}
                  />
                  <span className="text-sm font-medium text-foreground">
                    {isReasoningInProgress ? "Thinking..." : "Thought"}
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent className="flex items-center gap-2 mb-2">
                <div className="text-sm text-foreground">
                  <MessageContent content={reasoning!} />
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}

        {hasAgentActivity && (
          <div className="mb-4">
            <AgentTurns
              agentTurns={agentTurns!}
              isComplete={isAgentComplete || false}
            />
          </div>
        )}

        <div className="min-h-[1rem]">
          {content && content.length > 0 ? (
            <MessageContent content={content} />
          ) : isStreaming ? (
            <LoadingDots />
          ) : null}
        </div>

        <div className="flex items-center justify-between mt-2">
          <p className="text-xs opacity-70">{timestamp.toLocaleTimeString()}</p>
          {role === "assistant" && (
            <div className="absolute bottom-2 right-2 flex items-center space-x-2">
              {copied && (
                <p className="text-xs opacity-70 transition-opacity">Copied!</p>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopy}
                className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                {copied ? (
                  <Check className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
