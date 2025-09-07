import { Message as MessageData } from "@/types/chat";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef } from "react";
import { Message } from "./Message";

interface MessageListProps {
  messages: MessageData[];
  endRef: React.RefObject<HTMLDivElement | null>;
}

export function MessageList({ messages, endRef }: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div ref={scrollRef} className="overflow-y-auto py-6">
      <div className="">
        <AnimatePresence>
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center text-muted-foreground mt-8"
            >
              Start a conversation by typing a message below
            </motion.div>
          ) : (
            <div className="space-y-4">
              {messages.map((message) => (
                <Message key={message.id} {...message} />
              ))}
              <div ref={endRef} className="h-0" />
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
