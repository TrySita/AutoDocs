import type { CitationProperties } from "@/lib/utils/remarkCitations";
import type { ReactNode } from "react";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      // Allow using a custom <citation> element in JSX and in react-markdown components mapping
      citation: CitationProperties & { children?: ReactNode };
    }
  }
}

export {};

