"use client";

import debounce from "lodash.debounce"; // or use your own tiny debounce
import { useEffect, useMemo, useRef, useState } from "react";
import { useCustomSearchParams } from "./useSearchParams";

/**
 * Track the element most visible in the viewport and reflect it in the URL.
 * @param ids          Array of DOM ids you want to observe.
 * @param debounceMs   Delay before mutating the query string.
 */
export default function useActiveDefinition(
  ids: string[],
  rootId: string | null,
  debounceMs = 600,
) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const observers = useRef<Record<string, IntersectionObserver | null>>({});
  const [, setSearchParams] = useCustomSearchParams();

  // Write ?definitionId=<id> (replaceState so we don’t add history entries)
  const writeQuery = useMemo(
    () =>
      debounce((id: string | null) => {
        if (!id) return;
        setSearchParams(
          (prev) => {
            if (id === rootId) {
              prev.delete("definitionId");
              return prev;
            }
            prev.set("definitionId", id);
            return prev;
          },
          { replace: true },
        );
      }, debounceMs),
    [debounceMs, setSearchParams, rootId],
  );

  useEffect(() => {
    // Create one observer per id so we can un-observe cleanly on unmount.
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;

      const io = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveId(id); // updates React state
            writeQuery(id); // debounced URL update
          }
        },
        {
          root: null, // viewport
          threshold: 0.4, // >40 % visible counts as “current”
        },
      );

      io.observe(el);
      observers.current[id] = io;
    });

    // Cleanup on unmount / ids change
    return () => {
      Object.values(observers.current).forEach((io) => io?.disconnect());
      observers.current = {};
      writeQuery.cancel();
    };
  }, [ids, writeQuery]);

  return activeId;
}
