import { motion } from "framer-motion";
import { Loader2, Sparkles } from "lucide-react";

interface CompactionIndicatorProps {
  isCompacting: boolean;
}

export function CompactionIndicator({
  isCompacting,
}: CompactionIndicatorProps) {
  if (!isCompacting) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex items-center justify-center p-6"
    >
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 max-w-md">
        <div className="flex items-center space-x-3">
          <div className="flex-shrink-0">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            >
              <Sparkles className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </motion.div>
          </div>

          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <h3 className="text-sm font-medium text-blue-900 dark:text-blue-100">
                Compacting conversation...
              </h3>
              <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
            </div>

            <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
              Summarizing your conversation history to optimize context
            </p>
          </div>
        </div>

        {/* Progress bar animation */}
        <div className="mt-3 bg-blue-100 dark:bg-blue-800/30 rounded-full h-1.5 overflow-hidden">
          <motion.div
            className="h-full bg-blue-500 dark:bg-blue-400 rounded-full"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut",
            }}
          />
        </div>
      </div>
    </motion.div>
  );
}
