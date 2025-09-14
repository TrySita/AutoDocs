"use client";

import { Badge } from "@/components/common/shadcn-components/badge";
import { Button } from "@/components/common/shadcn-components/button";
import { Input } from "@/components/common/shadcn-components/input";
import { useDefinition } from "@/hooks/useApi";
import { useChat } from "@/hooks/useChat";
import { useSelectedDefinitionId, useSelectedFile } from "@/hooks/useSelected";
import { useQueryClient } from "@tanstack/react-query";
import { Bot, ExternalLink, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { CompactionIndicator } from "../chat/CompactionIndicator";
import { MessageList } from "../chat/MessageList";

interface ChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const SelectedDefinitionBadge = ({
  selectedDefinitionId,
  currentFile,
}: {
  selectedDefinitionId: string;
  currentFile: {
    filePath: string;
  };
}) => {
  const { data: currentDefinition } = useDefinition(
    parseInt(selectedDefinitionId),
  );

  return (
    <>
      {currentDefinition?.name} in {currentFile.filePath.split("/").pop()}
    </>
  );
};

const ChatDrawer: React.FC<ChatDrawerProps> = ({ isOpen, onClose }) => {
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const {
    messages,
    isLoading,
    isCompacting,
    handleSendMessage,
    handleDeleteConversation,
  } = useChat();

  const { fileData: currentFile } = useSelectedFile();

  const selectedDefinitionId = useSelectedDefinitionId();

  const onSendMessage = () => {
    if (!inputValue.trim() || isLoading) return;

    // Always allow sending messages (no auth required)
    handleSendMessage(inputValue.trim());
    setInputValue("");
  };

  // Refetch messages when drawer opens
  useEffect(() => {
    if (isOpen) {
      queryClient.invalidateQueries({ queryKey: ["messageHistory"] });
    }
  }, [isOpen, queryClient]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  if (!isOpen) return null;

  return (
    <div className="h-full w-full bg-card shadow-md flex flex-col overflow-y-auto relative">
      {/* Header */}
      <div className="p-4 border-border border-1 sticky top-0 right-0 w-full bg-background bg-opacity-100 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bot className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold text-foreground">Martin</h3>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 w-8 p-0"
            >
              <X className="w-4 h-4" />
            </Button>
            <Button onClick={handleDeleteConversation}>
              Delete conversation
            </Button>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <Badge variant="default" className="text-xs">
            Talking about:{" "}
            {selectedDefinitionId && currentFile ? (
              <SelectedDefinitionBadge
                selectedDefinitionId={selectedDefinitionId}
                currentFile={currentFile}
              />
            ) : (
              currentFile?.filePath.split("/").pop()
            )}
          </Badge>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 py-4 px-2 max-w-full overflow-y-auto">
        <MessageList endRef={messagesEndRef} messages={messages} />
        <CompactionIndicator isCompacting={isCompacting} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border sticky bottom-0 bg-background">
        <div className="flex space-x-2">
          <Input
            placeholder="Ask about this file..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                e.stopPropagation();
                onSendMessage();
              }
            }}
            className="flex-1"
            autoFocus
          />
          <Button
            onClick={onSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className="bg-primary hover:bg-primary-hover text-primary-foreground"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2 flex flex-row justify-between">
          Enter to send
        </p>
      </div>
    </div>
  );
};

export default ChatDrawer;
