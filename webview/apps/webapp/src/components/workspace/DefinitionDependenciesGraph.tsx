"use client";

import { Card } from "@/components/common/shadcn-components/card";
import { useDefinitions } from "@/hooks/useApi";
import { DefinitionMetadata } from "@/types/codebase";
import { getLayoutedElements } from "@/utils/getLayoutedElements";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  Node,
  NodeTypes,
  Panel,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { GitBranch } from "lucide-react";
import React, { useCallback, useLayoutEffect, useMemo } from "react";
import { CustomHandle } from "./CustomHandle";

const nodeWidth = 200; // Adjusted width for better layout
const nodeHeight = 80;

const DefinitionNode = ({
  data,
}: {
  data: {
    definitionData: DefinitionMetadata;
    main?: boolean;
  };
}) => (
  <Card
    className={`p-3 min-w-[180px] border-2 border-blue-200 hover:border-blue-400 cursor-pointer transition-colors ${
      data.main ? "border-primary" : ""
    }`}
  >
    <CustomHandle type="target" position={Position.Left} />
    <div className="flex items-center gap-2">
      <GitBranch className="h-4 w-4 text-blue-600" />
      <div className="flex-1 min-w-0">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">
            {data.definitionData.name}
          </p>
          <p className="text-xs text-muted-foreground truncate">
            {data.definitionData.file.filePath}
          </p>
        </div>
      </div>
    </div>
    <div className="mt-0">
      <span className="text-xs bg-primary px-1.5 py-0.5 rounded font-semibold text-white">
        {data.definitionData.definitionType}
      </span>
    </div>
    <CustomHandle type="source" position={Position.Right} />
  </Card>
);

type DefinitionRFNode = Node<{
  definitionData: DefinitionMetadata;
  main?: boolean;
}>;

const nodeTypes: NodeTypes = {
  definition: DefinitionNode,
};

interface DefinitionDependenciesGraphProps {
  definitionId: number;
  onDefinitionClick?: (definition: DefinitionMetadata) => void;
}

export const DefinitionDependenciesGraph: React.FC<
  DefinitionDependenciesGraphProps
> = ({ onDefinitionClick, definitionId }) => {
  const { data: definitions } = useDefinitions([definitionId]);
  const definition = definitions?.[0];

  const [definitionNodes, setDefinitionNodes, onDefinitionNodesChange] =
    useNodesState<DefinitionRFNode>([]);
  const [definitionEdges, setDefinitionEdges, onDefinitionEdgesChange] =
    useEdgesState<Edge>([]);

  const definitionsGraphElements = useMemo(() => {
    if (!definition) return { nodes: [], edges: [] };

    const nodes: DefinitionRFNode[] = [];
    const edges: Edge[] = [];

    // Add main file node
    nodes.push({
      id: definition.id.toString(),
      type: "definition",
      position: { x: 0, y: 0 },
      data: {
        definitionData: definition,
        main: true,
      },
      width: nodeWidth,
      height: nodeHeight,
    });

    definition.definitionDependencies.forEach((definitionNode) => {
      nodes.push({
        id: definitionNode.id.toString(),
        type: "definition",
        position: { x: 0, y: 0 },
        data: {
          definitionData: definitionNode.definition_toDefinitionId,
        },
        width: nodeWidth,
        height: nodeHeight,
      });
      edges.push({
        id: `${definition.id}-${definitionNode.id}`,
        source: definition.id.toString(),
        target: definitionNode.id.toString(),
        label: "depends on",
        labelStyle: {
          fill: "var(--foreground)",
          fontWeight: 500,
          fontSize: 11,
        },
        labelBgStyle: {
          fill: "var(--accent)",
          fillOpacity: 1,
          stroke: "var(--primary)",
          strokeWidth: 1.5,
        },
        labelBgPadding: [8, 12] as [number, number],
        labelBgBorderRadius: 12,
      });
    });

    definition.definitionDependents.forEach((definitionNode) => {
      nodes.push({
        id: definitionNode.id.toString(),
        type: "definition",
        position: { x: 0, y: 0 },
        data: {
          definitionData: definitionNode.definition_fromDefinitionId,
        },
        width: nodeWidth,
        height: nodeHeight,
      });
      edges.push({
        id: `${definitionNode.id}-${definition.id}`,
        source: definitionNode.id.toString(),
        target: definition.id.toString(),
        label: "is used by",
        labelStyle: {
          fill: "var(--foreground)",
          fontWeight: 500,
          fontSize: 11,
        },
        labelBgStyle: {
          fill: "var(--accent)",
          fillOpacity: 1,
          stroke: "var(--primary)",
          strokeWidth: 1.5,
        },
        labelBgPadding: [8, 12] as [number, number],
        labelBgBorderRadius: 12,
      });
    });

    const layoutedElements = getLayoutedElements(nodes, edges, "LR");

    return layoutedElements;
  }, [definition]);

  useLayoutEffect(() => {
    setDefinitionNodes([...definitionsGraphElements.nodes]);
    setDefinitionEdges([...definitionsGraphElements.edges]);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definitionsGraphElements]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: DefinitionRFNode) => {
      onDefinitionClick?.(node.data.definitionData);
    },
    [onDefinitionClick]
  );

  return (
    <div className="h-96 w-full">
      <div className="h-full w-full border">
        <ReactFlow<DefinitionRFNode>
          key={`definition-${definition?.id ?? "no-definition-yet"}`}
          data-testid="definition-graph"
          nodes={definitionNodes}
          edges={definitionEdges}
          onNodesChange={onDefinitionNodesChange}
          onEdgesChange={onDefinitionEdgesChange}
          proOptions={{
            hideAttribution: true,
          }}
          // onConnect={onConnect}
          onNodeClick={(_, node) => onNodeClick(_, node)}
          autoPanOnNodeFocus
          nodeTypes={nodeTypes}
          fitView
          zoomOnScroll={false}
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Controls />
          {/* <MiniMap /> */}
          <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
          <Panel
            position="top-left"
            className="bg-background/80 p-2 rounded-md"
          ></Panel>
        </ReactFlow>
      </div>
    </div>
  );
};
