import type { Options } from "rehype-sanitize";
import { defaultSchema } from "rehype-sanitize";

// Extend the default sanitize schema to allow our custom use of <cite>
// and its attributes that the remarkCitations plugin attaches. This ensures
// ReactMarkdown doesn't strip our nodes when sanitization is enabled.
export const citationSanitizeSchema: Options = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), "cite"],
  attributes: {
    ...(defaultSchema.attributes || {}),
    cite: ["text", "citationType", "fileId", "definitionId"],
  },
};
