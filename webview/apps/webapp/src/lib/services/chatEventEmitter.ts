import { OpenAIResponseEvent } from "@sita/shared";
import { EventEmitter } from "events";

// Plain EventEmitter instance (we enforce type-safety via helpers below)
export const chatEventEmitter = new EventEmitter();

// Event types for chat streaming

// Type-safe event emitter interface
interface ChatStreamEvent {
  kind: "stream";
  sessionId: string;
  event: OpenAIResponseEvent;
}

interface ChatErrorEvent {
  kind: "error";
  sessionId: string;
  error: string;
}

interface ChatCompleteEvent {
  kind: "complete";
  sessionId: string;
}

export type ChatEvent = ChatStreamEvent | ChatErrorEvent | ChatCompleteEvent;

// Helper functions for emitting events
export const emitChatStreamEvent = (
  sessionId: string,
  event: OpenAIResponseEvent,
) => {
  chatEventEmitter.emit(`chat:${sessionId}`, {
    kind: "stream",
    sessionId,
    event,
  });
};

export const emitChatErrorEvent = (sessionId: string, error: string) => {
  chatEventEmitter.emit(`chat:${sessionId}`, {
    kind: "error",
    sessionId,
    error,
  });
};

export const emitChatCompleteEvent = (sessionId: string) => {
  chatEventEmitter.emit(`chat:${sessionId}`, { kind: "complete", sessionId });
};

// Helper function to create unique session IDs
export const createChatSessionId = () =>
  `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
