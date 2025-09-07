import { AgentTurn } from "@/types/chat";
import { Hammer, MessageSquare } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../common/shadcn-components/accordion";
import { ToolCall } from "./ToolCall";

interface AgentTurnsProps {
  agentTurns: AgentTurn[];
  isComplete: boolean;
}

export function AgentTurns({ agentTurns, isComplete }: AgentTurnsProps) {
  const [openItems, setOpenItems] = useState<string[]>([]);

  // Auto-expand incomplete turns (similar to ToolCall auto-expansion)
  useEffect(() => {
    const incompleteTurns = agentTurns.filter((turn) => !turn.isComplete);
    if (incompleteTurns.length > 0) {
      const incompleteIds = incompleteTurns.map((turn) => turn.id);
      setOpenItems((prev) => [...new Set([...prev, ...incompleteIds])]);
    }
  }, [agentTurns]);

  if (!agentTurns || agentTurns.length === 0) {
    return null;
  }

  return (
    <Accordion
      type="multiple"
      value={openItems}
      onValueChange={setOpenItems}
      className="space-y-3"
    >
      {agentTurns.map((turn) => (
        <AccordionItem
          key={turn.id}
          value={turn.id}
          className="border rounded-lg bg-background/50"
        >
          <AccordionTrigger className="p-3">
            <div className="flex items-center gap-2">
              {turn.reasoning && (
                <MessageSquare className="w-4 h-4 text-blue-500" />
              )}
              {turn.toolCalls && turn.toolCalls.length > 0 && (
                <Hammer className="w-4 h-4 text-green-500" />
              )}
              Tools
            </div>
          </AccordionTrigger>

          <AccordionContent className="space-y-3">
            {turn.reasoning && (
              <div>
                <h5 className="text-sm font-medium mb-2">Reasoning:</h5>
                <div className="text-sm text-muted-foreground bg-muted/50 p-2 rounded">
                  {turn.reasoning}
                </div>
              </div>
            )}

            {turn.toolCalls &&
              turn.toolCalls.map((toolCall, idx) => (
                <ToolCall key={`${turn.id}-${idx}`} toolCall={toolCall} />
              ))}

            {turn.response && (
              <div>
                <h5 className="text-sm font-medium mb-2">Agent Response:</h5>
                <div className="text-sm bg-muted/50 p-2 rounded whitespace-pre-wrap">
                  {turn.response}
                </div>
              </div>
            )}
          </AccordionContent>
        </AccordionItem>
      ))}
    </Accordion>
  );
}
