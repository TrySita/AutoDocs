"use client";

import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

interface LoadingAnimationProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  color?: "primary" | "secondary" | "accent";
}

export function LoadingAnimation({
  className,
  size = "md",
  color = "primary",
}: LoadingAnimationProps) {
  const sizeClasses = {
    sm: "w-6 h-6",
    md: "w-8 h-8",
    lg: "w-12 h-12",
    xl: "w-16 h-16",
  };

  const colorClasses = {
    primary: "border-primary",
    secondary: "border-secondary",
    accent: "border-accent",
  };

  return (
    <div className={cn("flex items-center justify-center", className)}>
      <motion.div
        className={cn(
          "rounded-full border-2 border-transparent",
          sizeClasses[size],
          `${colorClasses[color]} border-t-current`,
        )}
        animate={{
          rotate: 360,
        }}
        transition={{
          duration: 1,
          repeat: Infinity,
          ease: "linear",
        }}
      />
    </div>
  );
}
