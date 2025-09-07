// Shared types used across multiple components

// Message type used in chat components
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface SitaUser {
  id: string;
  type: "registered" | "anonymous";
  remainingMessages: number; // used for rate limiting and tracking
  hasActiveSubscription: boolean; // true if user has pro plan, defaults to false
}

export type MessageLimits = {
  remaining: number;
  resetAt: Date;
};
