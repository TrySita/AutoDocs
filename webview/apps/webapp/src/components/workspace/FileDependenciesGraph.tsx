"use client";

import { Card } from "@/components/common/shadcn-components/card";
import { useAutoPanToNode } from "@/hooks/usePan";
import { useSelectedFile } from "@/hooks/useSelected";
import { getLayoutedElements } from "@/utils/getLayoutedElements";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MiniMap,
  Node,
  Panel,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { FileText } from "lucide-react";
import React, { useCallback, useLayoutEffect, useMemo } from "react";
import { CustomHandle } from "./CustomHandle";

const nodeWidth = 200; // Adjusted width for better layout
const nodeHeight = 80;

const FileNode = ({
  data,
}: {
  data: { path: string; language?: string; fileId: number; main?: boolean };
}) => (
  <Card
    className={`p-3 min-w-[180px] border-2 hover:border-primary/50 cursor-pointer transition-colors ${
      data.main ? "border-primary" : ""
    }`}
  >
    <CustomHandle type="target" position={Position.Top} />
    <div className="flex gap-2">
      <FileText className="h-4 w-4 text-primary" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {data.path.split("/").pop()}
        </p>
        <p className="text-xs text-muted-foreground truncate">{data.path}</p>
      </div>
    </div>
    {data.language && (
      <div className="mt-0">
        <span className="text-xs bg-primary px-1.5 py-0.5 rounded text-white font-semibold">
          {data.language}
        </span>
      </div>
    )}
    <CustomHandle type="source" position={Position.Bottom} />
  </Card>
);

const nodeTypes = {
  file: FileNode,
};

interface FileDependenciesGraphProps {
  onFileClick?: (fileId: number) => void;
}

export const FileDependenciesGraph: React.FC<FileDependenciesGraphProps> = ({
  onFileClick,
}) => {
  const { fileData } = useSelectedFile();

  const [fileNodes, setFileNodes, onFileNodesChange] = useNodesState<Node>([]);
  const [fileEdges, setFileEdges, onFileEdgesChange] = useEdgesState<Edge>([]);

  useAutoPanToNode(`${fileData?.id}-${fileData?.id}`);

  const fileGraphElements = useMemo(() => {
    if (!fileData) return { nodes: [], edges: [] };

    const nodes: Node[] = [];
    const edges: Edge[] = [];

    const rootFileId = `${fileData.id}-${fileData.id}`;

    // Add main file node
    nodes.push({
      id: rootFileId,
      type: "file",
      position: { x: 0, y: 0 },
      data: {
        path: fileData.filePath,
        language: fileData.language || "unknown",
        fileId: fileData.id,
        main: true,
      },
      // width: getNodeWidth((fileData.file_path as string).split("/").pop()),
      width: nodeWidth,
      height: nodeHeight,
    });

    fileData.fileDependencies.forEach((fileNode) => {
      const fileNodeId = `${fileData.id}-${fileNode.id}`;
      nodes.push({
        id: fileNodeId,
        type: "file",
        position: { x: 0, y: 0 },
        data: {
          path: fileNode.file_toFileId.filePath,
          language: fileNode.file_toFileId.language || "unknown",
          fileId: fileNode.file_toFileId.id,
          gist: fileNode.file_toFileId.aiSummary || "unknown",
        },
        // width: getNodeWidth((fileNode.file_path as string).split("/").pop()),
        width: nodeWidth,
        height: nodeHeight,
      });
      edges.push({
        id: `${fileData.id}-${fileData.id}-${fileNode.id}`,
        source: rootFileId,
        target: fileNodeId,
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

    fileData.fileDependents.forEach((fileNode) => {
      const fileNodeId = `${fileData.id}-${fileNode.id}`;
      nodes.push({
        id: fileNodeId,
        type: "file",
        position: { x: 0, y: 0 },
        data: {
          path: fileNode.file_fromFileId.filePath,
          language: fileNode.file_fromFileId.language || "unknown",
          fileId: fileNode.file_fromFileId.id,
        },
        // width: getNodeWidth((fileNode.file_path as string).split("/").pop()),
        width: nodeWidth,
        height: nodeHeight,
      });
      edges.push({
        id: `${fileData.id}-${fileNode.id}-${fileData.id}`,
        source: fileNodeId,
        target: rootFileId,
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

    const layoutedElements = getLayoutedElements(nodes, edges);

    return layoutedElements;
  }, [fileData]);

  useLayoutEffect(() => {
    setFileNodes([...fileGraphElements.nodes]);
    setFileEdges([...fileGraphElements.edges]);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileGraphElements]);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (
        node.data &&
        typeof node.data === "object" &&
        "fileId" in node.data &&
        onFileClick
      ) {
        onFileClick(node.data.fileId as number);
      }
    },
    [onFileClick],
  );
  return (
    <div className="h-96 w-full">
      <div className="h-full w-full border rounded-lg">
        <ReactFlow
          id="file-graph"
          nodes={fileNodes}
          proOptions={{
            hideAttribution: true,
          }}
          edges={fileEdges}
          onNodesChange={onFileNodesChange}
          onEdgesChange={onFileEdgesChange}
          // onConnect={onConnect}
          onNodeClick={onNodeClick}
          autoPanOnNodeFocus
          nodeTypes={nodeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
        >
          <Controls />
          <MiniMap />
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
