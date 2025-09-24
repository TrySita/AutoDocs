import type { Link, Root, RootContent } from "mdast";
import { toString } from "mdast-util-to-string";
import type { Plugin } from "unified";
import { SKIP, visit } from "unist-util-visit";

export interface CitationNode {
  type: "citation";
  data: {
    // Render as the standard HTML <cite> element for better typing
    hName: "cite";
    hProperties: {
      text: string;
      citationType: "file" | "definition";
      fileId?: string;
      definitionId?: string;
    };
  };
}

export type CitationProperties = CitationNode["data"]["hProperties"];

const remarkCitations: Plugin<[], Root> = () => {
  return (tree) => {
    visit(tree, "link", (node: Link, index, parent) => {
      if (!parent || typeof index !== "number") return;

      // Match: file::ID  or  file::ID:definition::ID (ID can be any non-space, non-colon sequence)
      const m = /^file::([^:\s]+)(?::definition::([^:\s]+))?$/.exec(
        node.url || "",
      );

      if (!m) return;

      const [, fileId, definitionId] = m;
      const text = toString(node); // renders the link's visible text

      const citationNode: CitationNode = {
        type: "citation",
        data: {
          hName: "cite",
          hProperties: {
            text,
            citationType: definitionId ? "definition" : "file",
            fileId,
            definitionId,
          },
        },
      };

      // Replace the link node with our custom node
      parent.children.splice(index, 1, citationNode as unknown as RootContent);

      return [SKIP, index];
    });

    // // Handle text nodes that might contain citations
    // visit(tree, 'text', (node: MdastText, index, parent) => {
    //   if (!parent || typeof index !== 'number') return;

    //   // Find all occurrences of file::ID or file::ID:definition::ID and splice them into citation nodes
    //   const citationPattern = /file::([^:\s\]\)]+)(?::definition::([^:\s\]\)]+))?/g;
    //   const original = node.value || '';

    //   let match: RegExpExecArray | null;
    //   let lastIndex = 0;
    //   const newNodes: RootContent[] = [];

    //   while ((match = citationPattern.exec(original)) !== null) {
    //     const [full, fileId, definitionId] = match;
    //     const start = match.index;
    //     const end = start + full.length;

    //     // Leading text before the citation
    //     if (start > lastIndex) {
    //       newNodes.push({
    //         type: 'text',
    //         value: original.slice(lastIndex, start),
    //       } as unknown as RootContent);
    //     }

    //     const citationNode: CitationNode = {
    //       type: 'citation',
    //       data: {
    //         hName: 'citation',
    //         hProperties: {
    //           text: 'reference',
    //           citationType: definitionId ? 'definition' : 'file',
    //           fileId,
    //           definitionId,
    //         },
    //       },
    //     };
    //     newNodes.push(citationNode as unknown as RootContent);

    //     lastIndex = end;
    //   }

    //   // Trailing text after the last citation
    //   if (lastIndex === 0) return; // no matches; leave node unchanged
    //   if (lastIndex < original.length) {
    //     newNodes.push({ type: 'text', value: original.slice(lastIndex) } as unknown as RootContent);
    //   }

    //   // Replace the single text node with the newly constructed sequence
    //   parent.children.splice(index, 1, ...newNodes);

    //   return [SKIP, index + newNodes.length];
    // });
  };
};

export default remarkCitations;
