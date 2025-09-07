"use client";

import { useNodesInitialized, useReactFlow } from "@xyflow/react";
import { useEffect } from "react";

export function useAutoPanToNode(nodeId?: string, zoom = 0.7) {
  const { getNode, setCenter, fitView } = useReactFlow();
  const ready = useNodesInitialized(); // ← all sizes measured?

  useEffect(() => {
    if (!nodeId || !ready) return;

    const node = getNode(nodeId);
    if (!node) return;

    // Preferred: keep current zoom but center on the node
    if (node.width && node.height) {
      setCenter(
        node.position.x + node.width / 2,
        node.position.y + node.height / 2,
        { zoom, duration: 400 }, // animate 0.4 s
      );
    } else {
      // Fallback: frame the node with a bit of space around it
      fitView({ nodes: [{ id: nodeId }], padding: 0.4, duration: 800 });
    }
  }, [nodeId, ready, getNode, setCenter, fitView, zoom]);
}
