export interface RelatedFile {
  file_path: string;
  file_id: string;
}

export interface RelatedDefinition {
  name: string;
  definition_id: string;
  file_id: string;
}

export interface SearchQuery {
  query: string;
  limit?: number;
  similarity_threshold?: number;
}

export interface ToolCall {
  id?: string;
  name: string;
  arguments: {
    searches: SearchQuery[];
  };
  status: "pending" | "executing" | "completed" | "failed" | "streaming";
  argumentsText?: string; // For streaming tool call arguments
  results?: {
    query: string;
    result: string;
  }[];
}

export interface AgentTurn {
  id: string;
  turnNumber: number;
  reasoning?: string;
  toolCalls?: ToolCall[];
  response?: string;
  isComplete: boolean;
  timestamp: Date;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  reasoning?: string;
  isReasoningComplete?: boolean; // Track when reasoning transitions from streaming to complete
  // New agentic properties
  agentTurns?: AgentTurn[];
  maxTurns?: number;
  isAgentComplete?: boolean;
}
