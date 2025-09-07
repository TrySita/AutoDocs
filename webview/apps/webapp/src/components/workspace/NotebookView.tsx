"use client";

import { Badge } from "@/components/common/shadcn-components/badge";
import { Button } from "@/components/common/shadcn-components/button";
import { Card, CardContent } from "@/components/common/shadcn-components/card";
// Removed Dialog (Docs/PRs) UI
import ReactMarkdown from "react-markdown";
// Removed unused tabs imports
import { useCustomSearchParams } from "@/hooks/useSearchParams";
import { Editor } from "@monaco-editor/react";
import { ReactFlowProvider } from "@xyflow/react";
import { Code2 } from "lucide-react";
import type { editor } from "monaco-editor";
import { useTheme } from "next-themes";
import { useParams, useRouter } from "next/navigation";
import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { DefinitionDependenciesGraph } from "./DefinitionDependenciesGraph";
import { FileDependenciesGraph } from "./FileDependenciesGraph";
// import useActiveDefinition from "@/hooks/useActiveDefinition";
import { SideBySideView } from "./SideBySideView";
// import FloatingOutlinePanel from "./FloatingOutlinePanel";
import { useFiles, usePackagesWithReadme } from "@/hooks/useApi";
import { useSelectedDefinitionId, useSelectedFile } from "@/hooks/useSelected";
import {
  DefinitionMetadata,
  FileDetailResponse,
  PackageResponse,
} from "@/types/codebase";

interface NotebookViewProps {
  fileData?: FileDetailResponse;
  isLoading?: boolean;
  onHighlightDefinition: (startLine: number, endLine: number) => void;
  onFileClick?: (fileId: number) => void;
  onDefinitionClick?: (definition: DefinitionMetadata) => void;
  currentView?: "docs" | "source";
}

const NotebookView = forwardRef<
  { switchToSourceTab: (startLine: number, endLine: number) => void },
  NotebookViewProps
>(
  (
    {
      fileData,
      isLoading,
      onHighlightDefinition,
      onFileClick,
      onDefinitionClick,
      currentView = "docs",
    },
    ref,
  ) => {
    const { theme } = useTheme();
    const router = useRouter();
    const params = useParams();
    const [searchParams] = useCustomSearchParams();
    const sourceEditorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
    const [isEditorMounted, setIsEditorMounted] = useState(false);

    const repoId = params.repoId as string;

    const selectedDefinitionId = useSelectedDefinitionId();

    // weird state stuff
    const scrolledToDefinition = useRef(false);
    const scrolledToFile = useRef(false);

    const handleDefinitionClick = (definition: DefinitionMetadata) => {
      if (onDefinitionClick) {
        onDefinitionClick(definition);
      }
      scrolledToDefinition.current = false; // reset scroll state
    };

    const [startLine, setStartLine] = useState<number | null>(null);

    useEffect(() => {
      scrolledToDefinition.current = false;
    }, [selectedDefinitionId, fileData?.id]);

    useEffect(() => {
      scrolledToFile.current = false;
    }, [fileData?.id]);

    useEffect(() => {
      if (!fileData?.id || scrolledToFile.current || selectedDefinitionId)
        return;
      const target = document.getElementById(`file-${fileData.id}`);
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        scrolledToFile.current = true;
      }
    }, [fileData?.id, selectedDefinitionId]);

    useEffect(() => {
      if (!selectedDefinitionId || scrolledToDefinition.current) return;
      const target = document.getElementById(selectedDefinitionId);
      if (target) {
        target.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
        scrolledToDefinition.current = true;
      }
    }, [selectedDefinitionId, fileData?.id]);

    useImperativeHandle(ref, () => ({
      switchToSourceTab: (startLine: number, endLine: number) => {
        // Navigate to source route with highlighting params
        const currentParams = new URLSearchParams(
          searchParams?.toString() || "",
        );
        currentParams.set("startLine", startLine.toString());
        currentParams.set("endLine", endLine.toString());
        const newUrl = `/workspace/${repoId}/source?${currentParams.toString()}`;
        router.push(newUrl);
      },
    }));

    // Handle highlighting when on source page with search params
    useEffect(() => {
      if (
        currentView === "source" &&
        searchParams &&
        isEditorMounted &&
        sourceEditorRef.current
      ) {
        const startLineParam = searchParams.get("startLine");
        const endLineParam = searchParams.get("endLine");

        if (startLineParam && endLineParam) {
          const startLine = parseInt(startLineParam);
          const endLine = parseInt(endLineParam);

          setTimeout(() => {
            if (sourceEditorRef.current) {
              const model = sourceEditorRef.current.getModel();
              if (model) {
                setStartLine(startLine);
                sourceEditorRef.current.revealLinesInCenter(startLine, endLine);
                const decorations =
                  sourceEditorRef.current.createDecorationsCollection([
                    {
                      range: {
                        startLineNumber: startLine,
                        startColumn: 1,
                        endLineNumber: endLine,
                        endColumn: model.getLineMaxColumn(endLine),
                      },
                      options: {
                        isWholeLine: true,
                        className: "highlighted-line",
                        inlineClassName: "highlighted-line-inline",
                      },
                    },
                  ]);
                setTimeout(() => {
                  decorations.clear();
                }, 3000);
              }
            }
          }, 200);
        }
      }
    }, [currentView, searchParams, isEditorMounted]);

    // Filter out definitions with no summary required
    const filteredDefinitions = fileData?.definitions ?? [];

    if (isLoading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
            <p className="text-muted-foreground">Loading file...</p>
          </div>
        </div>
      );
    }

    if (!fileData) {
      return <PackagesView onFileClick={onFileClick} />;
    }

    // Get language from file extension for syntax highlighting
    const getLanguage = (fileName: string): string => {
      const extension = fileName.split(".").pop()?.toLowerCase();

      switch (extension) {
        case "ts":
        case "tsx":
          return "typescript";
        case "js":
        case "jsx":
          return "javascript";
        case "py":
          return "python";
        case "java":
          return "java";
        case "cpp":
        case "cc":
        case "cxx":
          return "cpp";
        case "c":
          return "c";
        case "cs":
          return "csharp";
        case "go":
          return "go";
        case "rs":
          return "rust";
        default:
          return "plaintext";
      }
    };

    const language = getLanguage(fileData.filePath);
    const sourceLines = fileData.fileContent
      ? fileData.fileContent.split("\n")
      : [];

    // Extract code for a specific definition without context lines
    const getDefinitionCode = (startLine: number, endLine: number): string => {
      if (!sourceLines.length) return "// No source code available";

      const start = Math.max(0, startLine - 1);
      const end = Math.min(sourceLines.length, endLine);

      return sourceLines.slice(start, end).join("\n");
    };

    const handleViewSwitch = (view: "docs" | "source") => {
      const currentParams = new URLSearchParams(searchParams?.toString() || "");
      // Clear highlighting params when switching views
      currentParams.delete("startLine");
      currentParams.delete("endLine");
      router.push(`/workspace/${repoId}/${view}?${currentParams.toString()}`);
    };

    return (
      <div>
        <style>{`
        .highlighted-line {
          background-color: rgba(255, 255, 0, 0.15) !important;
          border-left: 4px solid #fbbf24 !important;
        }
        .highlighted-line-inline {
          background-color: rgba(255, 255, 0, 0.1) !important;
        }
      `}</style>
        <div className="w-full h-full px-6 py-6">
          {/* Tab-styled navigation */}
          <div className="mb-6">
            <div className="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground">
              <button
                onClick={() => handleViewSwitch("docs")}
                className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
                  currentView === "docs"
                    ? "bg-background text-foreground shadow"
                    : "hover:bg-background/60"
                }`}
              >
                Documentation
              </button>
              <button
                onClick={() => handleViewSwitch("source")}
                className={`inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
                  currentView === "source"
                    ? "bg-background text-foreground shadow"
                    : "hover:bg-background/60"
                }`}
              >
                Source Code
              </button>
            </div>
          </div>

          {currentView === "docs" && (
            <div className="space-y-8">
              {/* Floating Outline Panel, hiding this for now */}
              {/* <FloatingOutlinePanel
                fileData={fileData}
                filteredDefinitions={filteredDefinitions}
                activeDefinitionId={
                  selectedDefinitionId || `file-${fileData.id.toString()}`
                }
              /> */}
              {/* File Summary */}
              <Card className="shadow-sm" id={`file-${fileData.id.toString()}`}>
                <CardContent className="p-6">
                  <div className="mb-4">
                    <h1 className="text-2xl font-bold text-foreground mb-2">
                      {fileData.filePath}
                    </h1>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{fileData.language}</Badge>
                      <Badge variant="outline">
                        {filteredDefinitions.length} definitions
                      </Badge>
                    </div>
                  </div>

                  <ReactFlowProvider>
                    <FileDependenciesGraph onFileClick={onFileClick} />
                  </ReactFlowProvider>

                  {fileData.aiSummary && (
                    <div className="markdown pt-10 prose prose-sm max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        rehypePlugins={[rehypeRaw, rehypeSanitize]}
                      >
                        {fileData.aiSummary}
                      </ReactMarkdown>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Definition Sections */}
              {filteredDefinitions.length > 0 && (
                <div className="space-y-8">
                  <h2 className="text-xl font-semibold text-foreground">
                    Definitions
                  </h2>

                  {filteredDefinitions.map((def) => {
                    const definitionCode = getDefinitionCode(
                      def.startLine,
                      def.endLine,
                    );

                    return (
                      <Card
                        key={def.id}
                        className="shadow-sm"
                        id={def.id.toString()}
                      >
                        <CardContent className="p-0">
                          {/* Definition Header */}
                          <div className="px-4 border-b">
                            <div className="flex items-center justify-between pb-4">
                              <div className="flex items-center gap-3">
                                <h3 className="text-lg font-semibold text-foreground">
                                  {def.name}
                                </h3>
                                <Badge variant="default" className="text-white">
                                  {def.definitionType}{" "}
                                  {/* <span className="text-xs">({def.id})</span> */}
                                </Badge>
                                {/* {def.isExported && (
                                  <Badge variant="outline" className="text-xs">
                                    exported
                                  </Badge>
                                )} */}
                              </div>
                              <div className="flex items-center gap-3">
                                {/* Docs/PRs links and modals removed */}
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    onHighlightDefinition(
                                      def.startLine,
                                      def.endLine,
                                    )
                                  }
                                  className="text-xs"
                                >
                                  <Code2 className="w-3 h-3 mr-1" />
                                  View in Source
                                </Button>
                                <div className="text-sm text-muted-foreground">
                                  Lines {def.startLine}-{def.endLine}
                                </div>
                              </div>
                            </div>
                          </div>

                          <ReactFlowProvider>
                            <DefinitionDependenciesGraph
                              definitionId={def.id}
                              onDefinitionClick={handleDefinitionClick}
                            />
                          </ReactFlowProvider>

                          <div className="mb-4" />
                          <SideBySideView
                            def={def}
                            theme={theme}
                            definitionCode={definitionCode}
                          />
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {currentView === "source" && (
            <Card className="shadow-sm">
              <CardContent className="p-0">
                <div className="p-4 border-b bg-muted/20 flex justify-between">
                  <h2 className="text-lg font-semibold text-foreground">
                    {fileData.filePath}
                  </h2>
                </div>
                <Editor
                  height="calc(90vh - 200px)"
                  language={language}
                  value={fileData.fileContent || "// No source code available"}
                  theme={theme === "dark" ? "vs-dark" : "light"}
                  onMount={(editor) => {
                    sourceEditorRef.current = editor;
                    setIsEditorMounted(true);
                  }}
                  options={{
                    readOnly: true,
                    minimap: { enabled: true },
                    scrollBeyondLastLine: false,
                    fontSize: 13,
                    lineNumbers: "on",
                    renderWhitespace: "selection",
                    automaticLayout: true,
                    wordWrap: "on",
                    contextmenu: false,
                    folding: true,
                    lineDecorationsWidth: 10,
                    lineNumbersMinChars: 3,
                  }}
                  loading={
                    <div className="h-full flex items-center justify-center">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                    </div>
                  }
                />
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    );
  },
);

NotebookView.displayName = "NotebookView";

interface PackagesViewProps {
  onFileClick?: (fileId: number) => void;
}

const PackagesView = ({ onFileClick }: PackagesViewProps) => {
  const {
    data: packagesData,
    isLoading: packagesLoading,
    error: packagesError,
  } = usePackagesWithReadme();
  const { data: filesData } = useFiles();
  const [selectedPackage, setSelectedPackage] =
    useState<PackageResponse | null>(null);

  const nonRootPackages = packagesData?.filter(
    (pkg) => pkg.path !== "/" && pkg.path !== ".",
  );
  const rootPackage = packagesData?.find(
    (pkg) => pkg.path === "/" || pkg.path === ".",
  );

  if (packagesLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading packages...</p>
        </div>
      </div>
    );
  }

  if (packagesError) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center text-red-500">
          <p className="font-semibold mb-2">Error loading packages</p>
          <p className="text-sm">{packagesError.message}</p>
        </div>
      </div>
    );
  }

  // if (selectedPackage) {
  //   return (
  //     <div className="w-full h-full px-6 py-6">
  //       <div className="mb-6">
  //         <Button variant="outline" onClick={() => setSelectedPackage(null)} className="mb-4">
  //           ← Back to Packages
  //         </Button>
  //         <div className="flex items-center justify-between">
  //           <div>
  //             <h1 className="text-2xl font-bold text-foreground mb-2">{selectedPackage.name}</h1>
  //             <p className="text-muted-foreground">{selectedPackage.path}</p>
  //           </div>
  //           <Button
  //             onClick={handleNavigateToPackage}
  //             className="bg-primary hover:bg-primary-hover text-primary-foreground"
  //           >
  //             Navigate to Package
  //           </Button>
  //         </div>
  //       </div>

  //       <Card className="shadow-sm">
  //         <CardContent className="p-6">
  //           <div className="markdown prose prose-sm max-w-none">
  //             <ReactMarkdown
  //               remarkPlugins={[remarkGfm, remarkBreaks]}
  //               rehypePlugins={[rehypeRaw, rehypeSanitize]}
  //             >
  //               {selectedPackage.readme_content}
  //             </ReactMarkdown>
  //           </div>
  //         </CardContent>
  //       </Card>
  //     </div>
  //   );
  // }

  const handleNavigateToPackage = (selectedPackage: PackageResponse) => {
    if (!filesData || !onFileClick) return;

    // Find a file in this package to navigate to
    const packageFile = filesData.find((file) =>
      file.filePath.startsWith(selectedPackage.path),
    );

    if (packageFile) {
      onFileClick(packageFile.id);
    }
  };

  return (
    <div className="w-full h-full px-6 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground mb-2">
          Repository Packages
        </h1>
        <p className="text-muted-foreground">
          Select a package to view its documentation
        </p>
      </div>

      {!nonRootPackages || nonRootPackages.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-muted-foreground">
          <p>No packages found</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {nonRootPackages.map((pkg) => (
            <Card
              key={pkg.id}
              className="cursor-pointer hover:shadow-md transition-shadow"
              onClick={() => handleNavigateToPackage(pkg)}
            >
              <CardContent className="p-4">
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {pkg.name}
                </h3>
                <p className="text-sm text-muted-foreground mb-3">{pkg.path}</p>
                <div className="flex items-center gap-2">
                  {pkg.workspace_type && (
                    <Badge variant="outline">{pkg.workspace_type}</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {rootPackage?.readme_content ? (
        <Card className="shadow-sm mt-6">
          <CardContent className="p-6">
            <div className="markdown prose prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkBreaks]}
                rehypePlugins={[rehypeRaw, rehypeSanitize]}
              >
                {rootPackage?.readme_content}
              </ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
};

export default NotebookView;
