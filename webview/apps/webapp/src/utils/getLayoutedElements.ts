import { Edge, Node, Position } from "@xyflow/react";
import dagre from "dagre";

export const getLayoutedElements = <NodeType extends Node>(
  nodes: NodeType[],
  edges: Edge[],
  direction = "TB",
) => {
  const dagreGraph = new dagre.graphlib.Graph();

  dagreGraph.setDefaultNodeLabel(() => ({}));
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === "LR";
  dagreGraph.setGraph({ rankdir: direction, ranksep: 100 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: node.width,
      height: node.height,
    });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  nodes.forEach((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    node.targetPosition = isHorizontal ? Position.Left : Position.Top;
    node.sourcePosition = isHorizontal ? Position.Right : Position.Bottom;

    node.position = {
      x: nodeWithPosition.x - (node.width ?? 300) / 2,
      y: nodeWithPosition.y - (node.height ?? 200) / 2,
    };

    return node;
  });

  return { nodes, edges };
};
