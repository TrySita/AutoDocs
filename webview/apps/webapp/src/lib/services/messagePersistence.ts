import {
  anonymousUsers,
  conversations,
  messages,
  SupabaseDb,
} from "@sita/shared";
import { asc, desc, eq } from "drizzle-orm";

export interface StoredMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface MessageHistory {
  messages: StoredMessage[];
  summary: string | null;
  conversationId: string | null;
  characterCount: number;
}

const MAX_CHARS_BEFORE_COMPACTION = 2000;

// Ensure there is a stable anonymous user we can attach global conversations to
async function getOrCreateGlobalAnonymousUser(supabaseDb: SupabaseDb) {
  const existing = await supabaseDb
    .select({ id: anonymousUsers.id })
    .from(anonymousUsers)
    .where(eq(anonymousUsers.fingerprint, "global"))
    .limit(1);

  if (existing[0]) return existing[0].id;

  const created = await supabaseDb
    .insert(anonymousUsers)
    .values({ fingerprint: "global" })
    .returning({ id: anonymousUsers.id });

  return created[0].id;
}

// Get or create a single global conversation for all messages
async function getOrCreateGlobalConversation(supabaseDb: SupabaseDb) {
  // Try to get the most recent conversation (treating all as global)
  const conversationData = await supabaseDb
    .select({
      id: conversations.id,
      summary: conversations.summary,
      characterCount: conversations.characterCount,
    })
    .from(conversations)
    .orderBy(desc(conversations.createdAt))
    .limit(1);

  if (conversationData[0]) {
    return conversationData[0];
  }

  // Create a new conversation associated with a stable global anonymous user
  const globalAnonId = await getOrCreateGlobalAnonymousUser(supabaseDb);
  const newConversations = await supabaseDb
    .insert(conversations)
    .values({ anonymousUserId: globalAnonId })
    .returning({
      id: conversations.id,
      summary: conversations.summary,
      characterCount: conversations.characterCount,
    });

  return newConversations[0];
}

export async function getUserMessageHistory(
  supabaseDb: SupabaseDb,
): Promise<MessageHistory> {
  const conversation = await getOrCreateGlobalConversation(supabaseDb);

  if (!conversation) {
    return {
      messages: [],
      summary: null,
      conversationId: null,
      characterCount: 0,
    };
  }

  const data = await supabaseDb
    .select({
      role: messages.role,
      content: messages.content,
      timestamp: messages.timestamp,
    })
    .from(messages)
    .where(eq(messages.conversationId, conversation.id))
    .orderBy(asc(messages.timestamp));

  return {
    messages: data as StoredMessage[],
    summary: conversation.summary,
    conversationId: conversation.id,
    characterCount: conversation.characterCount || 0,
  };
}

export async function addMessage(
  supabaseDb: SupabaseDb,
  role: "user" | "assistant",
  content: string,
): Promise<void> {
  const conversation = await getOrCreateGlobalConversation(supabaseDb);

  if (!conversation) {
    throw new Error("Failed to get or create conversation");
  }

  await supabaseDb.insert(messages).values({
    conversationId: conversation.id,
    role,
    content,
    characterCount: content.length,
  });
}

export function shouldTriggerCompaction(characterCount: number): boolean {
  return characterCount >= MAX_CHARS_BEFORE_COMPACTION;
}

export async function updateConversationSummary(
  supabaseDb: SupabaseDb,
  conversationId: string,
  summary: string,
): Promise<void> {
  // Get the current messages that will remain after compaction
  const remainingMessages = await supabaseDb
    .select({ content: messages.content })
    .from(messages)
    .where(eq(messages.conversationId, conversationId))
    .orderBy(desc(messages.timestamp))
    .limit(1);

  const remainingChars = remainingMessages?.[0]?.content.length || 0;

  await supabaseDb
    .update(conversations)
    .set({
      summary,
      characterCount: summary.length + remainingChars,
    })
    .where(eq(conversations.id, conversationId));
}

export async function clearMessagesAfterCompaction(
  supabaseDb: SupabaseDb,
  conversationId: string,
): Promise<void> {
  // Mark older messages as not included in future context
  await supabaseDb
    .update(messages)
    .set({ includedInContext: false })
    .where(eq(messages.conversationId, conversationId));
}

export async function getRecentMessagesForContext(
  supabaseDb: SupabaseDb,
  conversationId: string,
  limit = 10,
): Promise<StoredMessage[]> {
  const data = await supabaseDb
    .select({
      role: messages.role,
      content: messages.content,
      timestamp: messages.timestamp,
    })
    .from(messages)
    .where(eq(messages.conversationId, conversationId))
    .orderBy(desc(messages.timestamp))
    .limit(limit);

  // Return in chronological order
  return data.reverse() as StoredMessage[];
}

export async function deleteConversation(
  supabaseDb: SupabaseDb,
  conversationId: string,
): Promise<void> {
  // Delete all messages for this conversation
  await supabaseDb
    .delete(messages)
    .where(eq(messages.conversationId, conversationId));

  // Delete the conversation
  await supabaseDb
    .delete(conversations)
    .where(eq(conversations.id, conversationId));
}
