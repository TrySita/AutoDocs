import OpenAI from "openai";
import { MessageHistory } from "./messagePersistence";

export interface ContextMessage {
  role: "user" | "assistant";
  content: string;
}
export class ContextBuilder {
  buildContext(messageHistory: MessageHistory): ContextMessage[] {
    const context: ContextMessage[] = [];

    if (messageHistory.summary) {
      context.push({
        role: "assistant",
        content: `Previous conversation summary: ${messageHistory.summary}`,
      });
    }

    for (const msg of messageHistory.messages) {
      context.push({
        role: msg.role,
        content: msg.content,
      });
    }

    return context;
  }

  formatForLLM(
    context: ContextMessage[],
    newUserMessage: string,
    activeCodeContext: string,
  ): OpenAI.Responses.ResponseInput {
    const formattedMessages: OpenAI.Responses.ResponseInput = [];

    for (const msg of context) {
      formattedMessages.push({
        role: msg.role,
        content: msg.content,
      });
    }

    const userContent = `${activeCodeContext}\n\n${newUserMessage}`;

    formattedMessages.push({
      role: "user",
      content: userContent,
    });

    return formattedMessages;
  }
}
