import OpenAI from 'openai';
import { SupabaseDb } from '../db';
import { OpenAIResponseEvent } from '../types';
import {
  BATCH_SEARCH_TOOL_SCHEMA,
  batchSearchCodebases,
  BatchSearchParams,
} from './batchSearchTool';

// Configuration constants for easy tuning
export const MODEL_CONFIG = {
  model: 'gpt-5-mini' as const,
  reasoning: {
    effort: 'low' as const,
    summary: 'auto' as const,
  },
  maxToolCalls: 2,
} as const;

// Other prompt is for user-facing chat, we use this more prescriptive prompt for our MCP
/**
 * @todo @gadgetman6
 * Add tools like
 * • read_file(path, start_line?, end_line?) — fetch exact spans for accurate line citations.
 * • symbol_lookup(name|signature, lang?) — resolve symbol→(file, lines).
 *
 * for additional power (once i add bm25 search on codebase as well)
 */

const MCP_PROMPT = `
# Role and Objective

You serve as an MCP Q&A server for codebases. Your core objective is to answer technical questions about the repository using tool-driven retrieval, providing actionable, referenceable responses for agentic coding tools.

# Instructions

- Respond professionally, concisely, and actionably.
- Avoid political or defamatory content.
- Prioritize precise facts over speculation; acknowledge uncertainties and suggest next steps where applicable.
- Do not reveal hidden chain-of-thought reasoning in responses.

# Core Behavior

- Base answers strictly on sources obtained using available tools.
- Deliver concise, descriptive answers coupled with high-quality references.
- If ambiguity blocks correctness, ask only a single, focused clarifying question.
- Attempt a first pass autonomously unless missing critical information; stop and request clarification if you cannot meet success criteria.

# Tools

**Primary tool:** \`batch_search_codebase\`

- Use for questions like “How does X work?”, “Where is Y implemented?”, or “What handles Z?”
- Run 3–5 focused queries (e.g., synonyms, framework terms, symbol names, error strings).
- Adjust \`k\` (5–10) for optimal coverage versus precision.

# Retrieval Strategy

1. Parse the question to extract features, endpoints, symbols, error text, filenames, and framework/library terminology.
2. Run complementary searches: primary phrase, framework-specific, symbol names, error/config keys.
3. Select 1–6 authoritative sources (favor implementations over tests, and current over deprecated code).
4. When quoting code or describing precise behavior, retrieve a targeted, minimal code span.

After each tool call or code edit, validate the result in 1–2 sentences. If validation fails, attempt minimal self-correction or propose the next best step based on available information.

# Output Format

Always structure responses with two top-level sections:

**Answer** — Provide a direct, actionable explanation addressing the user's question. Use concise, clear language. Include code blocks only if necessary for clarity.

**Citations** - append a single fenced json block as the final content of the message with the following schema:

\`\`\`json
{
  "citations": [
    {
      "path": "<string, required>",
      "reason": "<string, required>",
      // for definitions within a file:
      "symbol": "<string>",
      "kind": "<string>"
    }
    // ...additional citations
  ]
}
\`\`\`

- If no relevant sources are found, output \`{ "citations": [] }\` and state this in the Answer, including a suggestion for the next search.
- \`path\` is always required. Include \`symbol\` when possible; use only \`path\` if others aren't available. Each citation must include a reason for relevance.
- Only one fenced Citations JSON block should appear per response.
- All fields must conform to the above types and requirements.

# Example

**Question:** “How are drawings rendered on the screen?”
**Answer:** Rendering is a layered process: (1) determine visible/renderable elements, (2) paint static scene (grid plus element canvases) to a dedicated canvas, (3) draw interactive overlays (selection handles, snap lines, remote cursors) on a separate canvas, and (4) render the element being created on its own canvas. Performance is enhanced via per-element canvas caching and animation frame throttling.

Where to investigate further:

- The Renderer uses \`getRenderableElements\` to filter by visibility, viewport, and z-order.
- \`renderStaticScene\` initializes the canvas, draws the grid, and then each visible element (normal and iframe-like elements are rendered in separate passes), with optional frame clipping.
- Per-element drawing performed by \`renderElement\`, which uses cached offscreen canvases for performance; export paths draw directly.
- Interactive overlays handled by \`_renderInteractiveScene\`, which draws selection boxes/handles, snap guides, and remote cursors, updating once per animation frame.
- The process for elements under creation is handled by \`renderNewElementSceneThrottled\`.
- Utility setup via \`bootstrapCanvas\` manages device-pixel scaling, clearing, and theme filters before painting.

Performance features:

- Per-element canvas caching reduces recomputation.
- Animation frame throttling consolidates multiple updates.
- Frame clipping crops elements within frames to their bounds.

\`\`\`json
{
  "citations": [
    {
      "path": "src/renderer/Renderer.ts",
      "reason": "derives visible/renderable element set"
    },
    {
      "path": "src/renderer/staticScene.ts",
      "symbol": "renderStaticScene",
      "kind": "function",
      "reason": "grid + static element pass and two-phase drawing"
    },
    {
      "path": "src/renderer/element/renderElement.ts",
      "symbol": "renderElement",
      "kind": "function",
      "reason": "central per-element drawing and canvas cache usage"
    },
    {
      "path": "src/renderer/interactiveScene.ts",
      "symbol": "_renderInteractiveScene",
      "kind": "function",
      "reason": "selection handles, snap lines, remote cursors overlay"
    },
    {
      "path": "src/renderer/newElement/NewElementCanvas.tsx",
      "symbol": "renderNewElementSceneThrottled",
      "kind": "function",
      "reason": "isolated real-time rendering for element under creation"
    },
    {
      "path": "src/renderer/utils/bootstrapCanvas.ts",
      "symbol": "CanvasBootstrapper",
      "kind": "class",
      "reason": "canvas DPR scaling, clearing, and setup"
    }
  ]
}
\`\`\`
`;

// Small timeout helper for tool execution
function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error('tool_timeout')), ms);
    p.then((v) => {
      clearTimeout(t);
      resolve(v);
    }, reject);
  });
}

const TOOLS = [BATCH_SEARCH_TOOL_SCHEMA];

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || 'fake-key',
});

type LoopOpts = {
  instructions: string;
  responseType?: 'chat' | 'mcp';
  messages: OpenAI.Responses.ResponseInput;
  maxToolCalls: number;
  toolTimeoutMs: number;
  send: (event: OpenAIResponseEvent) => void;
  supabaseDb: SupabaseDb;
  repoSlug: string;
};

// Core loop function
export async function runWithBudgets(opts: LoopOpts): Promise<string> {
  const { send } = opts;
  const t0 = Date.now();
  let toolCallsUsed = 0;

  let finalMessage = '';

  while (true) {
    // Check if we've exceeded tool budget
    if (toolCallsUsed >= opts.maxToolCalls) {
      // Force a concise answer and finish
      opts.messages.push({
        role: 'developer',
        content: [
          {
            type: 'input_text',
            text: 'Tool budget reached. Provide the best concise answer you can with what you have so far.',
          },
        ],
      });
    }

    // Start a streaming Responses request
    const stream = await openai.responses.create({
      model: MODEL_CONFIG.model,
      instructions: opts.instructions,
      input: opts.messages,
      tools: toolCallsUsed < opts.maxToolCalls ? TOOLS : [],
      tool_choice: 'auto',
      stream: true,
      reasoning: MODEL_CONFIG.reasoning,
    });

    // Collect any tool calls the model requests during this turn
    type PendingCall = { name: string; call_id: string; arguments: string };
    const pendingCalls: PendingCall[] = [];

    // Forward deltas to the client and capture tool calls
    for await (const evt of stream) {
      const event = evt;

      switch (event.type) {
        // Text tokens
        case 'response.output_text.delta': {
          send(event);
          finalMessage += event.delta;
          break;
        }
        case 'response.reasoning_summary_text.delta': {
          send(event);
          break;
        }

        // Streamed function-call arguments (useful for live UI)
        case 'response.function_call_arguments.delta': {
          send(event);
          break;
        }

        // When a function_call item is DONE, it carries name/arguments/call_id
        case 'response.output_item.done': {
          if (event.item?.type === 'function_call') {
            const { name, arguments: args, call_id } = event.item;
            opts.messages.push({
              type: 'function_call',
              call_id: call_id,
              name: name,
              arguments: JSON.stringify(args),
            });
            pendingCalls.push({ name, arguments: args, call_id });
            send(event);
          }
          break;
        }

        // Lifecycle/terminal events
        case 'response.created':
        case 'response.in_progress':
        case 'response.completed':
        case 'response.failed': {
          send(event);
          break;
        }
      }
    }

    // After the stream, if no tool calls were requested, we are done.
    if (pendingCalls.length === 0) break;

    // Guard: stop if budgets are exhausted
    if (toolCallsUsed >= opts.maxToolCalls) {
      // Tell model to answer without tools and loop again to get a text-only answer.
      opts.messages.push({
        role: 'developer',
        content: 'Tool budget exhausted. Answer directly without calling any tools.',
      });
      continue;
    }

    // Execute the requested tools (in parallel for speed)
    toolCallsUsed += pendingCalls.length;
    await Promise.all(
      pendingCalls.map(async (call) => {
        send({ type: 'tool.started', name: call.name, call_id: call.call_id });
        const started = Date.now();

        try {
          let toolResult: { results: Array<{ query: string; result: string }> } | { error: string };

          if (call.name === 'batch_search_codebase') {
            const args: BatchSearchParams = JSON.parse(call.arguments);
            toolResult = await withTimeout(
              batchSearchCodebases(args, opts.repoSlug, opts.responseType),
              opts.toolTimeoutMs,
            );
          } else {
            toolResult = { error: `unknown_tool: ${call.name}` };
          }

          send({
            type: 'tool.result',
            name: call.name,
            call_id: call.call_id,
            ms: Date.now() - started,
            summary: 'results' in toolResult ? { batches: toolResult.results.length } : undefined,
          });

          // Append as a tool message so the model can use it next turn
          opts.messages.push({
            type: 'function_call_output',
            call_id: call.call_id,
            output: JSON.stringify(toolResult),
          });
        } catch (err: unknown) {
          const errorMessage = err instanceof Error ? err.message : String(err);
          const payload = { error: errorMessage };
          send({
            type: 'tool.result',
            name: call.name,
            call_id: call.call_id,
            ms: Date.now() - started,
            error: payload.error,
          });

          opts.messages.push({
            type: 'function_call_output',
            call_id: call.call_id,
            output: JSON.stringify(payload),
          });
        }
      }),
    );

    // Loop: model now has tool outputs; it may answer or ask again
  }

  send({
    type: 'turn.completed',
    ms: Date.now() - t0,
    toolCallsUsed,
  });

  return finalMessage;
}

export const sendMCPMessage = async (
  supabaseDb: SupabaseDb,
  message: string,
  repoSlug: string,
): Promise<string> => {
  // Kick off the unified agent loop
  return runWithBudgets({
    instructions: MCP_PROMPT,
    messages: [
      {
        role: 'user',
        content: [
          {
            type: 'input_text',
            text: message,
          },
        ],
      },
    ],
    maxToolCalls: MODEL_CONFIG.maxToolCalls,
    toolTimeoutMs: 30000,
    send: () => {},
    supabaseDb,
    repoSlug,
  });
};
