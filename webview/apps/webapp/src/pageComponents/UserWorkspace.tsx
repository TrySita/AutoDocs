"use client";

import ChatDrawer from "@/components/workspace/ChatDrawer";
import FileExplorer from "@/components/workspace/FileExplorer";
import FloatingChatIcon from "@/components/workspace/FloatingChatIcon";
import NotebookView from "@/components/workspace/NotebookView";
import { useCustomSearchParams } from "@/hooks/useSearchParams";
import { useSelectedFile } from "@/hooks/useSelected";
import { DefinitionMetadata } from "@/types/codebase";
import { isChatDrawerOpenAtom } from "@/utils/isChatOpen";
import { useAtom } from "jotai";
import { useParams } from "next/navigation";
import { useRef } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";

interface UserWorkspaceProps {
  view?: "docs" | "source";
}

const UserWorkspace = ({ view = "docs" }: UserWorkspaceProps) => {
  const [, setSearchParams] = useCustomSearchParams();
  const [isChatOpen, setIsChatOpen] = useAtom(isChatDrawerOpenAtom);
  const params = useParams();
  const notebookRef = useRef<{
    switchToSourceTab: (startLine: number, endLine: number) => void;
  }>(null);
  // Tracking removed

  const handleFileSelect = (fileId: number) => {
    setSearchParams({ fileId: fileId.toString() });
  };

  const handleNavigateToDefinition = (definition: DefinitionMetadata) => {
    setSearchParams({
      fileId: definition.fileId.toString(),
      definitionId: definition.id.toString(),
    });
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
    </div>
  );
};

export default UserWorkspace;
