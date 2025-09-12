"use client";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/common/shadcn-components/command";
import ChatDrawer from "@/components/workspace/ChatDrawer";
import FileExplorer from "@/components/workspace/FileExplorer";
import FloatingChatIcon from "@/components/workspace/FloatingChatIcon";
import NotebookView from "@/components/workspace/NotebookView";
import { useFiles } from "@/hooks/useApi";
import { useCustomSearchParams } from "@/hooks/useSearchParams";
import { useSelectedFile } from "@/hooks/useSelected";
import { DefinitionMetadata } from "@/types/codebase";
import { isChatDrawerOpenAtom } from "@/utils/isChatOpen";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai";
import { File, Hash } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useTRPC } from "@/lib/trpc/client";
import { currentRepoSlugAtom } from "@/lib/atoms/workspace";
import { useQuery } from "@tanstack/react-query";

interface UserWorkspaceProps {
  view?: "docs" | "source";
}

const UserWorkspace = ({ view = "docs" }: UserWorkspaceProps) => {
  const [, setSearchParams] = useCustomSearchParams();
  const [isChatOpen, setIsChatOpen] = useAtom(isChatDrawerOpenAtom);
  const [isCommandOpen, setIsCommandOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const { data: files } = useFiles();
  const trpc = useTRPC();
  const projectSlug = useAtomValue(currentRepoSlugAtom);
  const notebookRef = useRef<{
    switchToSourceTab: (startLine: number, endLine: number) => void;
  }>(null);

  // Keyboard shortcut for command palette
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsCommandOpen(true);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  // Debounce the search input to avoid spamming queries
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedQuery(searchQuery.trim());
    }, 250);
    return () => clearTimeout(handle);
  }, [searchQuery]);

  // Server-backed search using TRPC + FTS
  const enabledSearch =
    isCommandOpen && !!projectSlug && debouncedQuery.length > 0;

  const fileSearch = useQuery({
    ...trpc.analysis.search.files.queryOptions({
      projectSlug: projectSlug!,
      q: debouncedQuery,
      limit: 8,
      offset: 0,
    }),
    enabled: enabledSearch,
    staleTime: 5000,
  });

  const definitionSearch = useQuery({
    ...trpc.analysis.search.definitions.queryOptions({
      projectSlug: projectSlug!,
      q: debouncedQuery,
      limit: 8,
      offset: 0,
    }),
    enabled: enabledSearch,
    staleTime: 5000,
  });

  // Fallback to file list when no query
  const filteredItems = useMemo(() => {
    if (!debouncedQuery) {
      return { files: files || [], definitions: [] as DefinitionMetadata[] };
    }
    return {
      /**
       * @todo: hacky cast, add zod validation or fix SQL types
       */
      files: (fileSearch.data || []) as unknown as {
        id: number;
        filePath: string;
      }[],
      definitions: (definitionSearch.data || []) as DefinitionMetadata[],
    };
  }, [files, debouncedQuery, fileSearch.data, definitionSearch.data]);

  const handleFileSelect = (fileId: number) => {
    setSearchParams({ fileId: fileId.toString() });
    setIsCommandOpen(false);
  };

  const handleNavigateToDefinition = (definition: DefinitionMetadata) => {
    setSearchParams({
      fileId: definition.fileId.toString(),
      definitionId: definition.id.toString(),
    });
    setIsCommandOpen(false);
  };

  const handleDefinitionSelect = (definition: {
    fileId: number;
    id: number;
  }) => {
    setSearchParams({
      fileId: definition.fileId.toString(),
      definitionId: definition.id.toString(),
    });
    setIsCommandOpen(false);
  };

  const handleHighlightDefinition = (startLine: number, endLine: number) => {
    notebookRef.current?.switchToSourceTab(startLine, endLine);
  };

  // Fetch file data based on selected file ID
  const { fileData, isLoading, error } = useSelectedFile();

  return (
    <div className="h-full w-full bg-background flex relative overflow-hidden">
      <PanelGroup
        direction="horizontal"
        className="h-full w-full"
        autoSaveId="martin-chat-size"
      >
        {/* File Explorer Panel */}
        <Panel
          defaultSize={20}
          minSize={15}
          maxSize={30}
          className="bg-section-bg border-r border-border"
        >
          <FileExplorer
            onFileSelect={handleFileSelect}
            selectedFileId={fileData?.id}
            onSearchClick={() => setIsCommandOpen(true)}
          />
        </Panel>

        <PanelResizeHandle className="w-1 bg-border hover:bg-primary/20 transition-colors" />

        {/* Main Content Area */}
        <Panel defaultSize={isChatOpen ? 55 : 80} minSize={30}>
          <div className="h-full w-full overflow-auto">
            {/* Notebook-style Content */}
            {error ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-center text-red-500">
                  <p className="font-semibold mb-2">Error loading file</p>
                  <p className="text-sm">{error.message}</p>
                </div>
              </div>
            ) : (
              <NotebookView
                ref={notebookRef}
                fileData={fileData}
                isLoading={isLoading}
                onHighlightDefinition={handleHighlightDefinition}
                onFileClick={handleFileSelect}
                onDefinitionClick={handleNavigateToDefinition}
                currentView={view}
              />
            )}
          </div>
        </Panel>

        {/* Chat Drawer Panel */}
        {isChatOpen && (
          <>
            <PanelResizeHandle className="w-1 bg-border hover:bg-primary/20 transition-colors" />
            <Panel defaultSize={25} minSize={20} maxSize={50}>
              <ChatDrawer
                isOpen={isChatOpen}
                onClose={() => setIsChatOpen(false)}
              />
            </Panel>
          </>
        )}
      </PanelGroup>

      {/* Floating Chat Icon */}
      <FloatingChatIcon
        onClick={() => setIsChatOpen(true)}
        isVisible={!isChatOpen}
      />

      {/* Command Dialog */}
      <CommandDialog
        open={isCommandOpen}
        onOpenChange={setIsCommandOpen}
        title="Quick Navigation"
        description="Search files and definitions..."
        shouldFilter={false}
      >
        <CommandInput
          placeholder="Search files and definitions..."
          value={searchQuery}
          onValueChange={setSearchQuery}
        />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>

          <CommandGroup heading="Files">
            {filteredItems.files.map((file) => (
              <CommandItem
                key={`file-${file.id}`}
                value={`file-${file.id}`}
                onSelect={() => handleFileSelect(file.id)}
                className="flex items-center gap-2"
              >
                <File className="h-4 w-4" />
                <span className="flex-1 truncate">{file.filePath}</span>
              </CommandItem>
            ))}
          </CommandGroup>

          <CommandGroup heading="Definitions">
            {filteredItems.definitions.map((definition) => (
              <CommandItem
                key={`def-${definition.id}`}
                value={`def-${definition.id}`}
                onSelect={() => handleDefinitionSelect(definition)}
                className="flex items-center gap-2"
              >
                <Hash className="h-4 w-4" />
                <div className="flex-1">
                  <div className="font-medium">{definition.name}</div>
                  <div className="text-sm text-muted-foreground truncate">
                    {definition.file.filePath}
                  </div>
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </div>
  );
};

export default UserWorkspace;
