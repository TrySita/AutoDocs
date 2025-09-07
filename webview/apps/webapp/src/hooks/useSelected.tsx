"use client";

import { useSearchParams } from "next/navigation";
import { useFile } from "./useApi";

export const useSelectedFile = () => {
  const searchParams = useSearchParams()!;

  const selectedFileId = searchParams.get("fileId")
    ? parseInt(searchParams.get("fileId")!)
    : 0;

  const { data: fileData, isLoading, error } = useFile(selectedFileId);

  return { fileData, isLoading, error };
};

export const useSelectedDefinitionId = () => {
  const searchParams = useSearchParams()!;

  const selectedDefinitionId = searchParams.get("definitionId")
    ? searchParams.get("definitionId")
    : undefined;

  return selectedDefinitionId;
};
