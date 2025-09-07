import {
  ChatEvent,
  chatEventEmitter,
  createChatSessionId,
  emitChatCompleteEvent,
  emitChatErrorEvent,
  emitChatStreamEvent,
} from "@/lib/services/chatEventEmitter";
import { handleChatMessage } from "@/lib/services/chatHandler";
import { conversations } from "@sita/shared";
import { TRPCError } from "@trpc/server";
import { and, eq } from "drizzle-orm";
import { on } from "events";
import z from "zod";
import { publicProcedure, router } from "../init";

export const chatRouter = router({
  deleteConversation: publicProcedure
    .input(
      z.object({
        conversationId: z.string().optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      if (input.conversationId) {
        await ctx.supabaseDb
          .delete(conversations)
          .where(eq(conversations.id, input.conversationId));
      } else {
        /**
         * @todo add conversation-specific management, now we just delete all
         */
        await ctx.supabaseDb.delete(conversations);
      }
    }),

  sendMessage: publicProcedure
    .input(
      z.object({
        message: z.string().min(1),
        repoId: z.string(),
        source: z.string().optional(),
        currentFile: z.any().optional(),
        currentDefinition: z.any().optional(),
        pageContext: z.any().optional(),
        fileContext: z.any().optional(),
      }),
    )
    .subscription(async function* ({ input, ctx, signal }) {
      const sessionId = createChatSessionId();

      const workerAbort = new AbortController();
      signal?.addEventListener("abort", () => {
        workerAbort.abort();
      });

      try {
        // Start the chat processing in the background
        handleChatMessage({
          sessionId,
          input,
          ctx,
          emitEvent: emitChatStreamEvent,
          emitError: emitChatErrorEvent,
          emitComplete: emitChatCompleteEvent,
        }).catch((error) => {
          emitChatErrorEvent(sessionId, error?.message || "Unknown error");
        });

        for await (const [data] of on(chatEventEmitter, `chat:${sessionId}`)) {
          const evt = data as ChatEvent;

          if (evt.kind === "complete") {
            break;
          } else if (evt.kind === "error") {
            throw new TRPCError({
              code: "INTERNAL_SERVER_ERROR",
              message: evt.error,
            });
          }

          /**
           * @todo add tracked later to resume connection
           */

          yield evt.event;
        }
      } finally {
        workerAbort.abort();
      }
    }),
});
