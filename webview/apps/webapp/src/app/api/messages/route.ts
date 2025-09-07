import { getUserMessageHistory } from "@/lib/services/messagePersistence";
import { supabaseDb } from "@sita/shared";

// Force dynamic rendering - required for Cloudflare deployment where env vars are only available at runtime
export const dynamic = "force-dynamic";

export async function OPTIONS() {
  return new Response(null, {
    status: 200,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization, x-api-key",
    },
  });
}

export async function GET(_request: Request) {
  try {
    // No authentication required
    const messageHistory = await getUserMessageHistory(supabaseDb);

    const messages = messageHistory.messages.map((msg, index) => ({
      id: `${msg.role}-${index}-${msg.timestamp}`,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.timestamp),
    }));

    return Response.json(
      {
        messages,
        summary: messageHistory.summary,
        remaining: 999999, // Unlimited messages
        conversationId: messageHistory.conversationId,
      },
      {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, OPTIONS",
          "Access-Control-Allow-Headers":
            "Content-Type, Authorization, x-api-key",
        },
      },
    );
  } catch {
    return new Response("Internal Server Error", { status: 500 });
  }
}
