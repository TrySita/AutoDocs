import * as z from 'zod';
import { zodToJsonSchema } from 'zod-to-json-schema';
import { SupabaseDb } from '../db';
import { SearchItemSchema, type SemanticSearchResult } from '../types';
import { semanticSearch } from './semantic-search';

// Tool parameters schema
export const BatchSearchParameters = z
  .object({
    searches: z
      .array(SearchItemSchema)
      .min(1)
      .max(5)
      .describe('List of semantic searches to run in parallel'),
  })
  .strict();

export type BatchSearchParams = z.infer<typeof BatchSearchParameters>;

// Convert to JSON Schema for OpenAI tools
export const BATCH_SEARCH_TOOL_SCHEMA = {
  type: 'function' as const,
  name: 'batch_search_codebase',
  description: 'Run parallel semantic searches across the codebase',
  parameters: zodToJsonSchema(BatchSearchParameters),
  strict: false,
};

function formatSearchResult(
  result: SemanticSearchResult,
  resultIndex: number,
  responseType?: 'chat' | 'mcp',
): string {
  const similarity = (result.similarity * 100).toFixed(1);

  if (result.entity_type === 'file' && result.file) {
    const definitions = result.file.definitions || [];
    const definitionsList =
      definitions.length > 0
        ? `\nDefinitions in this file:\n${definitions.map((def) => `- ${def.name} (${def.definitionType}) [ID: ${def.id}]`).join('\n')}`
        : '';

    return `**File Result #${resultIndex + 1}** (Similarity: ${similarity}%)
File: ${result.file.filePath}
Language: ${result.file.language}
File ID: ${result.file.id}
${definitionsList}
${responseType === 'chat' ? `Citation: [${result.file.filePath}](file::${result.file.id})` : ''}
Summary: ${result.file.aiSummary || 'No summary available.'}`;
  }

  if (result.entity_type === 'definition' && result.definition) {
    return `**Definition Result #${resultIndex + 1}** (Similarity: ${similarity}%)
Name: ${result.definition.name}
Type: ${result.definition.definitionType}
File: ${result.definition.file.filePath}
File ID: ${result.definition.file.id}
Definition ID: ${result.definition.id}
${responseType === 'chat' ? `Citation: [${result.definition.name}](file::${result.definition.file.id}:definition::${result.definition.id})` : ''}
Lines: ${result.definition.startLine}-${result.definition.endLine}
Summary: ${result.definition.aiSummary || 'No summary available.'}`;
  }

  return `Unknown result type`;
}

export async function batchSearchCodebases(
  args: BatchSearchParams,
  repoSlug: string,
  responseType?: 'chat' | 'mcp',
): Promise<{
  results: Array<{
    query: string;
    result: string;
    // metadata: SemanticSearchResult[]
  }>;
}> {
  const searches = args.searches;

  // Execute parallel semantic search
  const searchResults = await semanticSearch(searches, repoSlug);

  // Format results for each query
  const results = searchResults.map((queryResults, queryIndex) => {
    const search = searches[queryIndex];

    if (queryResults.length === 0) {
      return {
        query: search.query,
        result: `No results found for query: "${search.query}"`,
        // metadata: [],
      };
    }

    const formattedResults = queryResults
      .map((result, resultIndex) => formatSearchResult(result, resultIndex, responseType))
      .join('\n\n');

    return {
      query: search.query,
      result: `Found ${queryResults.length} results for "${search.query}":\n\n${formattedResults}`,
      // metadata: queryResults,
    };
  });

  return { results };
}
