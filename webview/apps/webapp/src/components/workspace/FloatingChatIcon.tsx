"use client";

import { Button } from "@/components/common/shadcn-components/button";
import { MessageCircle } from "lucide-react";
import { useRef, useState } from "react";
import Draggable, { DraggableData, DraggableEvent } from "react-draggable";

interface FloatingChatIconProps {
  onClick: () => void;
  isVisible: boolean;
}

const FloatingChatIcon: React.FC<FloatingChatIconProps> = ({
  onClick,
  isVisible,
}) => {
  const [dragStartPosition, setDragStartPosition] = useState({ x: 0, y: 0 });
  const nodeRef = useRef(null);

  const handleStart = (_e: DraggableEvent, data: DraggableData) => {
    setDragStartPosition({ x: data.x, y: data.y });
  };

  const handleStop = (_e: DraggableEvent, data: DraggableData) => {
    // Calculate distance moved
    const distance = Math.sqrt(
      Math.pow(data.x - dragStartPosition.x, 2) +
        Math.pow(data.y - dragStartPosition.y, 2),
    );

    // If moved less than 5 pixels, consider it a click
    if (distance < 5) {
      onClick();
    }
  };

  if (!isVisible) {
    return null;
  }

  return (
    <Draggable
      nodeRef={nodeRef}
      onStart={handleStart}
      onStop={handleStop}
      defaultPosition={{
        x: window.outerWidth - 150,
        y: window.outerHeight - 200,
      }}
    >
      <div
        ref={nodeRef}
        className="fixed w-14 h-14 z-50 cursor-move"
        style={{ touchAction: "none" }}
      >
        <Button
          className="w-full h-full rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg transition-colors duration-200"
          title="AI Chat Assistant"
          onMouseDown={(e) => e.preventDefault()} // Prevent button click during drag
        >
          <MessageCircle className="w-6 h-6" />
        </Button>
      </div>
    </Draggable>
  );
};

export default FloatingChatIcon;
