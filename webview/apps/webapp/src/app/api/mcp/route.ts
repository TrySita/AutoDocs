import { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import { supabaseDb, sendMCPMessage } from "@sita/shared";
import { createMcpHandler, withMcpAuth } from "mcp-handler";
import { z } from "zod";

export const runtime = "nodejs";
export const dynamic = "force-dynamic"; // don't cache MCP traffic

// Build an MCP server and register one tool + one prompt.
const baseHandler = createMcpHandler(
  (server) => {
    // 1) Tool: codebase-qna (only one param: question)
    server.tool(
      "codebase-qna",
      "Answer repo-scoped questions. Returns an answer describing files and definitions related to the question.",
      { question: z.string().describe("The question to answer") },
      async ({ question }, extra) => {
        if (
          !extra.authInfo?.extra?.repoId ||
          !(typeof extra.authInfo?.extra?.repoId === "string")
        ) {
          return {
            isError: true,
            content: [
              {
                type: "text",
                text: 'Missing repo ID. Add header "x-repo-id: <REPO_ID>',
              },
            ],
          };
        }

        const answer = await sendMCPMessage(
          supabaseDb,
          question,
          extra.authInfo.extra.repoId,
        );

        return {
          content: [{ type: "text", text: answer }],
        };
      },
    );
  },
  {
    serverInfo: {
      name: "Deep search codebase",
      version: "1.0.0",
    },
    instructions:
      "You are a precise codebase assistant. When the user asks about code in this repository: 1) Call the tool codebase-qna with the user's question. 2) In your final answer: state the conclusion first, then list supporting {path, defName}. 3) If confidence is low, suggest concrete follow-up questions. Never hallucinate paths or symbol names.",
  },
  // Adapter options
  {
    basePath: "/api", // our handler lives at /api/mcp
    maxDuration: 60, // seconds for SSE; HTTP requests return immediately
    verboseLogs: true,
    disableSse: false,
  },
);

// Wrap to pass through x-repo-id header into authInfo.extra.repoId (no auth logic)
const handler = withMcpAuth(baseHandler, async (req): Promise<AuthInfo> => {
  const repoId = req.headers.get("x-repo-id");
  return {
    token: "",
    clientId: "repo-header",
    scopes: [],
    extra: { repoId },
  };
});

// Streamable HTTP + SSE on the same handler (adapter auto-detects)
export { handler as GET, handler as POST };
