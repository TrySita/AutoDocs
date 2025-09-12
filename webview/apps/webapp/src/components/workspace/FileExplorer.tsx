"use client";

import { useFiles } from "@/hooks/useApi";
import { FileResponse } from "@/types/codebase";
import { File, Folder, FolderOpen, Search } from "lucide-react";
import { useEffect, useState } from "react";
import TreeView, {
  flattenTree,
  INode,
  NodeId,
} from "react-accessible-treeview";

interface FileExplorerProps {
  onFileSelect: (fileId: number) => void;
  selectedFileId?: number;
  onSearchClick?: () => void;
}
interface TreeNode {
  name: string;
  fileId?: number; // File ID for leaf nodes (files only, undefined for folders)
  children?: TreeNode[];
}

function getAncestorIds(data: INode[], id: string | number): NodeId[] {
  const map = new Map(data.map((n) => [n.id, n.parent])); //  id → parentId
  const ids: NodeId[] = [];
  let current = map.get(id);
  while (current != null) {
    // walk up until the (hidden) root
    ids.push(current);
    current = map.get(current);
  }
  return ids;
}

const buildPathMapping = (
  node: TreeNode,
  path: string = "",
  nodePathToFileId: Map<string, number>
) => {
  const currentPath = path ? `${path}/${node.name}` : node.name;
  if (node.fileId) {
    nodePathToFileId.set(currentPath, node.fileId);
  }
  if (node.children) {
    node.children.forEach((child: TreeNode) =>
      buildPathMapping(child, currentPath, nodePathToFileId)
    );
  }
};

const FileExplorer: React.FC<FileExplorerProps> = ({
  onFileSelect,
  selectedFileId,
  onSearchClick,
}) => {
  const { data: files, isLoading, error } = useFiles();

  const buildFileTree = (files: FileResponse[]): TreeNode => {
    const root: TreeNode = { name: "", children: [] };

    files.forEach((file) => {
      const pathParts = file.filePath.split("/").filter((part) => part !== "");
      let current = root;

      pathParts.forEach((part, index) => {
        if (!current.children) {
          current.children = [];
        }

        let child = current.children.find((c) => c.name === part);
        if (!child) {
          const isFile = index === pathParts.length - 1;
          child = {
            name: part,
            fileId: isFile ? file.id : undefined,
            children: isFile ? undefined : [],
          };
          current.children.push(child);
        }
        current = child;
      });
    });

    return root;
  };

  const fileTree = buildFileTree(files ?? []);
  const data = flattenTree(fileTree);

  // Create a mapping from node path to file ID
  const nodePathToFileId = new Map<string, number>();

  buildPathMapping(fileTree, "", nodePathToFileId);

  // Helper function to get full path of a node
  const getNodePath = (node: INode): string => {
    if (node.parent === 0) return node.name;
    const parentNode = data.find((n) => n.id === node.parent);
    if (!parentNode) return node.name;
    const parentPath = getNodePath(parentNode);
    return parentPath ? `${parentPath}/${node.name}` : node.name;
  };

  const getNodeIdFromFileId = (fileId: number): NodeId | undefined => {
    // Find the node that corresponds to this fileId
    for (const node of data) {
      if (!node.isBranch) {
        // Only check leaf nodes (files)
        const nodePath = getNodePath(node);
        const nodeFileId = nodePathToFileId.get(nodePath);
        if (nodeFileId === fileId) {
          return node.id;
        }
      }
    }
    return undefined;
  };

  const selectedNodeId = selectedFileId
    ? getNodeIdFromFileId(selectedFileId)
    : undefined;
  const [expandedIds, setExpandedIds] = useState<NodeId[]>(
    selectedNodeId ? getAncestorIds(data, selectedNodeId) : []
  );

  useEffect(() => {
    if (selectedNodeId) {
      setExpandedIds([...getAncestorIds(data, selectedNodeId)]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedFileId, selectedNodeId]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        Loading files...
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center text-red-500">
        Error: {error.message}
      </div>
    );
  }

  if (!files || files.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        No files found
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-border">
        <div
          className="relative cursor-pointer"
          onClick={() => onSearchClick?.()}
        >
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <div className="pl-10 pr-4 py-2 text-sm text-muted-foreground cursor-text rounded-md border border-input transition-colors">
            Search (⌘K)
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-2">
        <TreeView
          data={data}
          aria-label="File Explorer"
          expandedIds={expandedIds}
          selectedIds={selectedNodeId ? [selectedNodeId] : []}
          onNodeSelect={(props) => {
            if (!props.isBranch) {
              const nodePath = getNodePath(props.element);
              const fileId = nodePathToFileId.get(nodePath);
              if (fileId) {
                onFileSelect(fileId);
              }
            }
          }}
          nodeRenderer={({
            element,
            isBranch,
            isExpanded,
            getNodeProps,
            level,
          }) => {
            const isSelected = selectedNodeId === element.id;

            return (
              <div
                {...getNodeProps()}
                className={`flex items-center space-x-2 py-1 px-2 rounded cursor-pointer hover:bg-black/10 ${
                  isSelected ? "bg-primary/10 text-primary" : ""
                }`}
                style={{ paddingLeft: `${20 * (level - 1)}px` }}
              >
                {isBranch ? (
                  isExpanded ? (
                    <FolderOpen className="w-4 h-4 text-blue-500" />
                  ) : (
                    <Folder className="w-4 h-4 text-blue-500" />
                  )
                ) : (
                  <File className="w-4 h-4 text-muted-foreground" />
                )}
                <span className="text-sm truncate">{element.name}</span>
              </div>
            );
          }}
        />
      </div>
    </div>
  );
};

export default FileExplorer;
