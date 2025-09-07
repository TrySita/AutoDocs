import { ContextBuilder } from "@/lib/services/contextBuilder";
import {
  addMessage,
  getRecentMessagesForContext,
  getUserMessageHistory,
} from "@/lib/services/messagePersistence";
// Authentication removed - no longer needed
import { DefinitionDetailResponse, FileDetailResponse } from "@/types/codebase";
import {
  MODEL_CONFIG,
  OpenAIResponseEvent,
  runWithBudgets,
} from "@sita/shared";

type PageContext = {
  title: string;
  description: string;
  url: string;
  content: string;
};

type FileContext = {
  languageId: string;
  lineCount: number;
  content: string;
  fileName: string;
};

const SYSTEM_PROMPT = ({ repoSlug }: { repoSlug: string }) => `
You are Martin, a knowledgeable and approachable software engineer who acts as a friendly onboarding guide for new team members. Your purpose is to help new hires understand and navigate a codebase, resolve technical queries, and offer supportive onboarding guidance.

You are currently working in the ${repoSlug} codebase

General questions are welcome, but you must avoid engaging in political discussions or issuing defamatory statements.

You will receive user questions, sometimes with additional information about files or code definitions. Use any available context, including codebase search results, to provide precise, actionable, and context-aware answers—incorporating information returned from codebase searches if present.

After each guidance or code-related response, validate that the explanation is accurate and addresses the user's onboarding needs; revise or clarify if the answer is incomplete or unclear.

## Guidelines
1. Make responses concise and stay focused on directly answering the user's question, particularly with onboarding clarity—as though you are assisting a colleague learning the system for the first time.
2. If a question is code-specific and you do not receive any source code context, clearly state that you lack access to the codebase and cannot address code-specific queries.

## Tool usage
ALWAYS use the batch_search_codebase tool when users ask about code, implementation, or need help understanding functionality.

Examples:
- User: "How does authentication work?" → searches: [{"query": "authentication login", "k": 10}, {"query": "user session management", "k": 8}]
- User: "Where is API error handling?" → searches: [{"query": "api error handling", "k": 8}, {"query": "exception middleware", "k": 6}]

## Reference Format
- When referencing code, files, or definitions, ALWAYS use the citation format below (markdown link syntax):
  - \`[link description](file::<file_id>)\`
  - \`[link description](file::<file_id>:definition::<definition_id>)\`
- Only cite files or definitions if the corresponding file/definition IDs are provided.
- Never omit the description in the citation link.
- Don't use citations without following this exact format, as they will not be processed correctly.

### Example Citations
- [Session management utilities](file::42)
- [User authentication middleware](file::23:definition::7)
`;

interface HandleChatMessageParams {
  sessionId: string;
  input: {
    message: string;
    repoId: string;
    source?: string;
    currentFile?: FileDetailResponse;
    currentDefinition?: DefinitionDetailResponse;
    pageContext?: PageContext;
    fileContext?: FileContext;
  };
  ctx: any;
  emitEvent: (sessionId: string, event: OpenAIResponseEvent) => void;
  emitError: (sessionId: string, error: string) => void;
  emitComplete: (sessionId: string) => void;
}

export async function handleChatMessage({
  sessionId,
  input,
  ctx,
  emitEvent,
  emitError,
  emitComplete,
}: HandleChatMessageParams): Promise<string | void> {
  const { supabaseDb } = ctx;

  try {
    // No authentication required - proceed directly

    const {
      message: userMessage,
      currentFile: currentFileInput,
      currentDefinition: currentDefinitionInput,
      source,
      pageContext,
      fileContext,
      repoId,
    } = input;

    if (!repoId) {
      emitError(sessionId, "Not currently viewing a repository");
      return;
    }

    const currentFile = currentFileInput as FileDetailResponse | undefined;
    const currentDefinition = currentDefinitionInput as
      | DefinitionDetailResponse
      | undefined;

    if (!userMessage || typeof userMessage !== "string") {
      emitError(sessionId, "Invalid message");
      return;
    }

    const contextBuilder = new ContextBuilder();
    const messageHistory = await getUserMessageHistory(supabaseDb);

    const send = (event: OpenAIResponseEvent) => emitEvent(sessionId, event);

    // Build context for the LLM
    let contextMessages = messageHistory.messages;
    if (messageHistory.conversationId && messageHistory.summary) {
      contextMessages = await getRecentMessagesForContext(
        supabaseDb,
        messageHistory.conversationId,
        10,
      );
    }

    const contextForLLM = {
      ...messageHistory,
      messages: contextMessages,
    };
    const context = contextBuilder.buildContext(contextForLLM);

    const CURRENT_CONTEXT_PROMPT = `${
      currentFile
        ? `<<ACTIVE_FILE_CONTEXT>>
File path: ${currentFile.filePath}
File ID: ${currentFile.id}
File source code: \`\`\`typescript
${currentFile.fileContent}
\`\`\`

File summary: ${currentFile.aiSummary || "No summary available"}
<<END_ACTIVE_FILE_CONTEXT>>
`
        : ""
    }

${
  currentDefinition
    ? `<<ACTIVE_DEFINITION_CONTEXT>>
Definition name: ${currentDefinition.name}
Definition ID: ${currentDefinition.id}
Definition source code: \`\`\`typescript
${currentDefinition.sourceCode}
\`\`\`
Definition summary: ${currentDefinition.aiSummary || "No summary available"}
<<END_ACTIVE_DEFINITION_CONTEXT>>
`
    : ""
}`;

    const formattedMessages = contextBuilder.formatForLLM(
      context,
      userMessage,
      CURRENT_CONTEXT_PROMPT,
    );

    // Build system prompt
    let systemPrompt = SYSTEM_PROMPT({ repoSlug: repoId });

    // Add page context for Chrome extension messages
    if (source === "chrome_extension" && pageContext) {
      systemPrompt += `

# Current Page Context
The user is currently viewing: ${pageContext.title}
URL: ${pageContext.url}

Page content:
${pageContext.content}

Use this page context to provide more relevant and specific answers when the user asks about the current page.`;
    }

    // Add file context for VS Code extension messages
    if (source === "vscode_extension") {
      systemPrompt += `

# VS Code Extension Context
The user is asking from within VS Code. Be aware that they are in a development environment and may be asking about code they're currently working on.`;

      if (fileContext) {
        systemPrompt += `

The user is currently editing a file:
File: ${fileContext.fileName}
Language: ${fileContext.languageId}
Lines: ${fileContext.lineCount}

File content:
\`\`\`${fileContext.languageId}
${fileContext.content}
\`\`\`

Use this file context to provide more relevant and specific answers when the user asks about the current file they're editing.`;
      }
    }

    // Track full response for persistence
    let fullResponse = "";

    // Kick off the unified agent loop
    await runWithBudgets({
      instructions: systemPrompt,
      responseType: "chat",
      messages: formattedMessages,
      maxToolCalls: MODEL_CONFIG.maxToolCalls,
      toolTimeoutMs: 30000,
      send: (event) => {
        send(event);
        // Accumulate text for persistence
        if (event.type === "response.output_text.delta") {
          fullResponse += event.delta;
        }
      },
      supabaseDb,
      repoSlug: repoId,
    });

    // Save messages to database
    await addMessage(supabaseDb, "user", userMessage);
    await addMessage(supabaseDb, "assistant", fullResponse);
    // No message count tracking needed

    send({ type: "done", done: true });
    emitComplete(sessionId);

    return fullResponse;
  } catch (e) {
    console.error("Agent loop failed:", e);
    emitError(sessionId, e instanceof Error ? e.message : "Unknown error");
  }
}
