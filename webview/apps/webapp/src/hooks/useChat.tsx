"use client";

import { currentRepoSlugAtom } from "@/lib/atoms/workspace";
import { useTRPC } from "@/lib/trpc/client";
import { AgentTurn, Message, ToolCall } from "@/types/chat";
import { MessageLimits } from "@/types/shared";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSubscription } from "@trpc/tanstack-react-query";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import { ResponseOutputItem } from "openai/resources/responses/responses.mjs";
import { startTransition, useCallback, useEffect, useState } from "react";

interface MessageHistoryResponse {
  messages: Message[];
  summary: string | null;
  conversationId: string;
}

const fetchMessageHistory = async (): Promise<MessageHistoryResponse> => {
  const response = await fetch("/api/messages", {
    headers: {
      "Content-Type": "application/json",
      "x-fingerprint": "00000000-0000-0000-0000-000000000000",
    },
  });

  if (!response.ok) {
    // Return empty history if fetch fails
    return {
      messages: [],
      summary: null,
      conversationId: "default",
    };
  }

  const data = (await response.json()) as MessageHistoryResponse;

  const parsedMessages = (data.messages || []).map((msg: Message) => {
    return {
      ...msg,
      timestamp: new Date(msg.timestamp),
    };
  });

  return {
    messages: parsedMessages,
    summary: data.summary,
    conversationId: data.conversationId,
  };
};

// Atom to store current conversation messages (includes streaming messages)
const currentMessagesAtom = atom<Message[]>([]);

// Atom to store conversation summary
const conversationSummaryAtom = atom<string | null>(null);

// Message history atom with query
const useMessageHistory = () => {
  return useQuery({
    queryKey: ["messageHistory"],
    queryFn: () => fetchMessageHistory(),
    enabled: true, // Always enabled
  });
};

const useMessageLimits = (): {
  data: MessageLimits | null;
  isLoading: boolean;
} => {
  // Always return unlimited messages
  return {
    data: {
      remaining: 999999,
      resetAt: new Date(Date.now() + 24 * 60 * 60 * 1000),
    },
    isLoading: false,
  };
};

// Main chat hook
export const useChat = () => {
  const trpc = useTRPC();
  const messageHistory = useMessageHistory();
  const [messages, setMessages] = useAtom(currentMessagesAtom);
  const setSummary = useSetAtom(conversationSummaryAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [isCompacting, setIsCompacting] = useState(false);
  const [currentMessage, setCurrentMessage] = useState<string>("");
  const [shouldSubscribe, setShouldSubscribe] = useState(false);
  const [assistantMessageId, setAssistantMessageId] = useState<string>("");

  const [currentTurn, setCurrentTurn] = useState<AgentTurn | null>(null);
  const [currentToolCall, setCurrentToolCall] = useState<ToolCall | null>(null);

  const repoId = useAtomValue(currentRepoSlugAtom);

  const queryClient = useQueryClient();

  const { data, isLoading: isMessageLimitsLoading } = useMessageLimits();

  const remainingMessages = data?.remaining ?? 999999;
  const canSendMessage = true; // Always allow sending messages

  const { mutateAsync: deleteConversation } = useMutation(
    trpc.chat.deleteConversation.mutationOptions({
      onSuccess: () => {
        // Invalidate message history to refresh after deletion
        queryClient.invalidateQueries({ queryKey: ["messageHistory"] });
      },
    }),
  );

  // Sync fetched message history with current messages
  useEffect(() => {
    if (messageHistory.data) {
      // Avoid overwriting in-flight local streaming state.
      // Only hydrate from server on initial load (or after explicit clear).
      if (!isLoading && !shouldSubscribe && messages.length === 0) {
        setMessages(messageHistory.data.messages);
        setSummary(messageHistory.data.summary);
      }
    }
  }, [
    messageHistory.data,
    setMessages,
    setSummary,
    isLoading,
    shouldSubscribe,
    messages.length,
  ]);

  // tRPC subscription using correct pattern
  useSubscription(
    trpc.chat.sendMessage.subscriptionOptions(
      {
        message: currentMessage,
        repoId: repoId || "martin",
      },
      {
        enabled: shouldSubscribe && !!currentMessage && !!repoId,
        onData: (data) => {
          // Handle new unified SSE streaming events
          if (data.type === "response.output_text.delta") {
            // Main response text - mark reasoning as complete when output starts
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      content: msg.content + data.delta,
                      isReasoningComplete: true,
                    }
                  : msg,
              ),
            );
          } else if (data.type === "response.reasoning_summary_text.delta") {
            // Accumulate reasoning summary - use startTransition for performance
            startTransition(() => {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessageId
                    ? {
                        ...msg,
                        reasoning: (msg.reasoning || "") + data.delta,
                      }
                    : msg,
                ),
              );
            });
          } else if (data.type === "response.function_call_arguments.delta") {
            // Initialize current tool call if needed
            setCurrentToolCall((prevToolCall) => {
              let updatedToolCall = prevToolCall;
              if (!updatedToolCall) {
                updatedToolCall = {
                  id: "",
                  name: "",
                  arguments: { searches: [] },
                  status: "streaming",
                  argumentsText: "",
                };
              }

              // Accumulate arguments text
              updatedToolCall.argumentsText =
                (updatedToolCall.argumentsText || "") + data.delta;

              // Initialize current turn if needed
              setCurrentTurn((prevTurn) => {
                let updatedTurn = prevTurn;
                if (!updatedTurn) {
                  updatedTurn = {
                    id: `turn-${Date.now()}`,
                    turnNumber: 1,
                    isComplete: false,
                    timestamp: new Date(),
                  };
                }

                // Update current turn with streaming tool call
                const finalTurn: AgentTurn = {
                  id: updatedTurn.id,
                  turnNumber: updatedTurn.turnNumber,
                  reasoning: updatedTurn.reasoning,
                  toolCalls: [updatedToolCall],
                  isComplete: false,
                  timestamp: updatedTurn.timestamp,
                };

                startTransition(() => {
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? {
                            ...msg,
                            agentTurns: [
                              ...(msg.agentTurns ?? []).filter(
                                (turn) => turn.id !== finalTurn.id,
                              ),
                              finalTurn,
                            ],
                          }
                        : msg,
                    ),
                  );
                });

                return updatedTurn;
              });

              return updatedToolCall;
            });
          } else if (data.type === "response.output_item.done") {
            const functionCallItem: ResponseOutputItem = data.item;

            // Tool call completed
            if (functionCallItem.type === "function_call") {
              setCurrentToolCall((prevToolCall) => {
                if (!prevToolCall) return null;

                const updatedToolCall = {
                  id: functionCallItem.id,
                  name: functionCallItem.name,
                  arguments: JSON.parse(functionCallItem.arguments),
                  status: "pending" as const,
                  argumentsText: prevToolCall.argumentsText,
                  results: prevToolCall.results,
                };

                // Update message state to show the completed tool call
                setCurrentTurn((prevTurn) => {
                  const updatedTurn: AgentTurn = {
                    id: prevTurn?.id || `turn-${Date.now()}`,
                    turnNumber: prevTurn?.turnNumber || 1,
                    reasoning: prevTurn?.reasoning,
                    toolCalls: [updatedToolCall],
                    isComplete: false,
                    timestamp: prevTurn?.timestamp || new Date(),
                  };

                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? {
                            ...msg,
                            reasoning: msg.reasoning + "\n\n",
                            agentTurns: [
                              ...(msg.agentTurns ?? []).filter(
                                (turn) => turn.id !== updatedTurn.id,
                              ),
                              updatedTurn,
                            ],
                          }
                        : msg,
                    ),
                  );

                  return updatedTurn;
                });

                return updatedToolCall;
              });
            }
          } else if (data.type === "tool.started") {
            console.log("Tool started:", data);
            setCurrentToolCall((prevToolCall) => {
              if (prevToolCall && prevToolCall.id === data.call_id) {
                const updatedToolCall: ToolCall = {
                  id: data.call_id,
                  name: data.name,
                  arguments: prevToolCall.arguments,
                  status: "executing" as const,
                  argumentsText: prevToolCall.argumentsText,
                  results: prevToolCall.results,
                };

                setCurrentTurn((prevTurn) => {
                  const updatedTurn: AgentTurn = {
                    id: prevTurn?.id || `turn-${Date.now()}`,
                    turnNumber: prevTurn?.turnNumber || 1,
                    reasoning: prevTurn?.reasoning,
                    toolCalls: [updatedToolCall],
                    isComplete: false,
                    timestamp: prevTurn?.timestamp || new Date(),
                  };

                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? {
                            ...msg,
                            agentTurns: [
                              ...(msg.agentTurns ?? []).filter(
                                (turn) => turn.id !== updatedTurn.id,
                              ),
                              updatedTurn,
                            ],
                          }
                        : msg,
                    ),
                  );

                  return updatedTurn;
                });

                return updatedToolCall;
              }
              return prevToolCall;
            });
          } else if (data.type === "tool.result") {
            console.log("Tool result received:", data);
            setCurrentToolCall((prevToolCall) => {
              if (prevToolCall && prevToolCall.id === data.call_id) {
                const updatedToolCall: ToolCall = {
                  id: prevToolCall.id,
                  name: prevToolCall.name,
                  arguments: prevToolCall.arguments,
                  status: data.error
                    ? ("failed" as const)
                    : ("completed" as const),
                  argumentsText: prevToolCall.argumentsText,
                  results: data.error
                    ? [{ query: "error", result: data.error }]
                    : undefined,
                };

                setCurrentTurn((prevTurn) => {
                  const updatedTurn: AgentTurn = {
                    id: prevTurn?.id || `turn-${Date.now()}`,
                    turnNumber: prevTurn?.turnNumber || 1,
                    reasoning: prevTurn?.reasoning,
                    toolCalls: [updatedToolCall],
                    isComplete: true,
                    timestamp: prevTurn?.timestamp || new Date(),
                  };

                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantMessageId
                        ? {
                            ...msg,
                            agentTurns: [
                              ...(msg.agentTurns ?? []).filter(
                                (turn) => turn.id !== updatedTurn.id,
                              ),
                              updatedTurn,
                            ],
                          }
                        : msg,
                    ),
                  );

                  return updatedTurn;
                });

                // Reset for next potential turn
                setCurrentTurn(null);
                return null;
              }
              return prevToolCall;
            });
          } else if (data.type === "turn.completed") {
            console.log("Turn completed:", data);
            // Tool usage is complete, final text should follow
          } else if (data.type === "compacting") {
            setIsCompacting(true);
          } else if (data.type === "compactionComplete") {
            setIsCompacting(false);
          } else if (data.type === "error") {
            console.error("Stream error:", data.message);

            // Try to parse as upgrade required error
            try {
              const errorData = JSON.parse(data.message);
              if (errorData.type === "upgrade_required") {
                const upgradeMessage: Message = {
                  id: `upgrade-${Date.now()}`,
                  role: "assistant",
                  content:
                    errorData.message +
                    "\n\n[Upgrade to Pro](/account/subscription)",
                  timestamp: new Date(),
                };
                setMessages((prev) => [...prev, upgradeMessage]);
                setIsLoading(false);
                setShouldSubscribe(false);
                return;
              }
            } catch {
              // Not a JSON error, handle as regular error
            }

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      content: `Sorry, an error occurred: ${data.message}`,
                      isStreaming: false,
                    }
                  : msg,
              ),
            );
            setIsLoading(false);
            setShouldSubscribe(false);
          } else if (data.type === "done") {
            setMessages((prev) =>
              prev.map((msg) => {
                if (msg.id === assistantMessageId) {
                  return {
                    ...msg,
                    isStreaming: false,
                    isAgentComplete: true,
                  };
                }
                return msg;
              }),
            );

            setIsLoading(false);
            setIsCompacting(false);
            setShouldSubscribe(false);
          }
        },
        onError: (error) => {
          console.error("tRPC subscription error:", error);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId
                ? {
                    ...msg,
                    content: "Sorry, I encountered an error. Please try again.",
                    isStreaming: false,
                  }
                : msg,
            ),
          );
          setIsLoading(false);
          setIsCompacting(false);
          setShouldSubscribe(false);
        },
      },
    ),
  );

  const handleSendMessage = useCallback(
    (message: string) => {
      const trimmedMessage = message.trim();
      if (!trimmedMessage || isLoading) return;

      const messageId = `msg-${Date.now()}`;
      const assistantId = `assistant-${Date.now()}`;

      // Add user message immediately
      setMessages((prev) => [
        ...prev,
        {
          id: messageId,
          role: "user" as const,
          content: trimmedMessage,
          timestamp: new Date(),
        },
      ]);

      // Add placeholder assistant message
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant" as const,
          content: "",
          timestamp: new Date(),
          isStreaming: true,
        },
      ]);

      setIsLoading(true);
      setCurrentMessage(trimmedMessage);
      setAssistantMessageId(assistantId);
      // Debug: ensure we know which repo the message is for
      setShouldSubscribe(true);
    },
    [isLoading, setMessages],
  );

  const handleDeleteConversation = useCallback(async () => {
    try {
      // Delete without specifying conversationId - will delete all
      await deleteConversation({});

      // Prevent stale hydration: set cache to empty immediately
      queryClient.setQueryData<MessageHistoryResponse>(["messageHistory"], {
        messages: [],
        summary: null,
        conversationId: "default",
      });

      // Clear local state
      setMessages([]);
      setSummary(null);

      // Ensure we pull fresh server state (which will create a new empty conversation)
      await queryClient.refetchQueries({ queryKey: ["messageHistory"] });
    } catch (error) {
      console.error("Failed to delete conversation:", error);
    }
  }, [deleteConversation, setMessages, setSummary, queryClient]);

  return {
    messages,
    isLoading,
    isMessageLimitLoading: isMessageLimitsLoading,
    isCompacting,
    handleSendMessage,
    handleDeleteConversation,
    canSendMessage,
    anonymousUser: null,
    remainingMessages,
  };
};
