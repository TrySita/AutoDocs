import OpenAI from 'openai';
import z from 'zod';

export type SemanticSearchResult = {
  entity_type: 'file' | 'definition';
  entity_id: number;
  distance: number;
  similarity: number;
  // File-specific fields
  file?: {
    id: number;
    filePath: string;
    language: string;
    fileContent: string;
    createdAt: string;
    updatedAt: string;
    aiSummary: string | null;
    definitions?: Array<{
      id: number;
      name: string;
      definitionType: string;
    }>;
  };
  // Definition-specific fields
  definition?: {
    id: number;
    name: string;
    definitionType: string;
    startLine: number;
    endLine: number;
    docstring: string | null;
    sourceCode: string | null;
    isExported: number;
    aiSummary: string | null;
    file: {
      id: number;
      filePath: string;
      language: string;
    };
  };
};

/**
 * Search query configuration
 */
export const SearchItemSchema = z
  .object({
    query: z.string().describe('The search query to find relevant code/docs'),
    k: z.number().int().min(1).max(100).default(10).describe('Number of results to return (1-100)'),
  })
  .strict();

export type SearchQuery = z.infer<typeof SearchItemSchema>;

/**
 * Parallel semantic search result
 */
export type ParallelSearchResult = {
  query: string;
  results: SemanticSearchResult[];
  count: number;
};

// New streaming events for unified SSE approach with Responses API
export type OpenAIResponseEvent =
  | Extract<
      OpenAI.Responses.ResponseStreamEvent,
      | { type: 'response.output_text.delta' }
      | { type: 'response.reasoning_summary_text.delta' }
      | { type: 'response.function_call_arguments.delta' }
      | { type: 'response.output_item.done' }
      | { type: 'response.created' }
      | { type: 'response.in_progress' }
      | { type: 'response.completed' }
      | { type: 'response.failed' }
    >
  | { type: 'tool.started'; name: string; call_id: string }
  | {
      type: 'tool.result';
      name: string;
      call_id: string;
      ms: number;
      summary?: { batches: number };
      error?: string;
    }
  | { type: 'turn.completed'; ms: number; toolCallsUsed: number }
  | { type: 'compacting'; compacting: boolean }
  | { type: 'compactionComplete'; compactionComplete: boolean }
  | { type: 'error'; message: string }
  | { type: 'done'; done: boolean };
