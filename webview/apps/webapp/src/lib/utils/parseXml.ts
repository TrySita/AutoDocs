import { RelatedDefinition, RelatedFile } from "@/types/chat";

export const parseXMLContent = (
  content: string,
): {
  content: string;
  relatedFiles: RelatedFile[];
  relatedDefinitions: RelatedDefinition[];
} => {
  // Extract main content from message tags
  const messageMatch = content.match(/<message>([\s\S]*?)<\/message>/);
  const mainContent = messageMatch ? messageMatch[1].trim() : content;

  // Extract related files
  const relatedFiles: RelatedFile[] = [];
  const filesMatch = content.match(
    /<related_files>([\s\S]*?)<\/related_files>/,
  );
  if (filesMatch) {
    const fileMatches = filesMatch[1].match(/<file>([\s\S]*?)<\/file>/g);
    if (fileMatches) {
      fileMatches.forEach((fileMatch) => {
        const pathMatch = fileMatch.match(/<file_path>([\s\S]*?)<\/file_path>/);
        const idMatch = fileMatch.match(/<file_id>([\s\S]*?)<\/file_id>/);
        if (pathMatch && idMatch) {
          relatedFiles.push({
            file_path: pathMatch[1].trim(),
            file_id: idMatch[1].trim(),
          });
        }
      });
    }
  }

  // Extract related definitions
  const relatedDefinitions: RelatedDefinition[] = [];
  const defsMatch = content.match(
    /<related_definitions>([\s\S]*?)<\/related_definitions>/,
  );
  if (defsMatch) {
    const defMatches = defsMatch[1].match(
      /<definition>([\s\S]*?)<\/definition>/g,
    );
    if (defMatches) {
      defMatches.forEach((defMatch) => {
        const nameMatch = defMatch.match(/<name>([\s\S]*?)<\/name>/);
        const idMatch = defMatch.match(
          /<definition_id>([\s\S]*?)<\/definition_id>/,
        );
        const fileIdMatch = defMatch.match(/<file_id>([\s\S]*?)<\/file_id>/);
        if (nameMatch && idMatch) {
          relatedDefinitions.push({
            name: nameMatch[1].trim(),
            definition_id: idMatch[1].trim(),
            file_id: fileIdMatch ? fileIdMatch[1].trim() : "",
          });
        }
      });
    }
  }

  return { content: mainContent, relatedFiles, relatedDefinitions };
};
