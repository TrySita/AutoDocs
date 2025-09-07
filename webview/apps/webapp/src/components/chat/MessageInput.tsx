import { Button } from "@/components/common/shadcn-components/button";
import { Textarea } from "../common/shadcn-components/textarea";

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function MessageInput({
  value,
  onChange,
  onSend,
  isLoading,
  disabled = false,
  placeholder = "Type your message...",
}: MessageInputProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSend();
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="flex space-x-2">
        <Textarea
          value={value}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !disabled) {
              e.preventDefault();
              onSend();
            }
          }}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={isLoading || disabled}
          className="flex-1 bg-card border border-primary/20 focus:ring-2 focus:ring-primary"
        />
        <Button type="submit" disabled={isLoading || !value.trim() || disabled}>
          Send
        </Button>
      </div>
    </form>
  );
}
