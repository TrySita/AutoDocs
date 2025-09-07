import { relations } from "drizzle-orm/relations";
import {
  definitionDependencies,
  definitions,
  fileDependencies,
  files,
  imports,
  packages,
  references,
  repositories,
} from "./schema";

export const packagesRelations = relations(packages, ({ one, many }) => ({
  repository: one(repositories, {
    fields: [packages.repositoryId],
    references: [repositories.id],
  }),
  files: many(files),
  imports: many(imports),
}));

export const repositoriesRelations = relations(repositories, ({ many }) => ({
  packages: many(packages),
}));

export const filesRelations = relations(files, ({ one, many }) => ({
  package: one(packages, {
    fields: [files.packageId],
    references: [packages.id],
  }),
  definitions: many(definitions),
  imports: many(imports),
  fileDependencies_toFileId: many(fileDependencies, {
    relationName: "fileDependencies_toFileId_files_id",
  }),
  fileDependencies_fromFileId: many(fileDependencies, {
    relationName: "fileDependencies_fromFileId_files_id",
  }),
}));

export const definitionsRelations = relations(definitions, ({ one, many }) => ({
  file: one(files, {
    fields: [definitions.fileId],
    references: [files.id],
  }),
  references_targetDefinitionId: many(references, {
    relationName: "references_targetDefinitionId_definitions_id",
  }),
  references_sourceDefinitionId: many(references, {
    relationName: "references_sourceDefinitionId_definitions_id",
  }),
  definitionDependencies_toDefinitionId: many(definitionDependencies, {
    relationName: "definitionDependencies_toDefinitionId_definitions_id",
  }),
  definitionDependencies_fromDefinitionId: many(definitionDependencies, {
    relationName: "definitionDependencies_fromDefinitionId_definitions_id",
  }),
}));

export const importsRelations = relations(imports, ({ one }) => ({
  package: one(packages, {
    fields: [imports.targetPackageId],
    references: [packages.id],
  }),
  file: one(files, {
    fields: [imports.fileId],
    references: [files.id],
  }),
}));

export const fileDependenciesRelations = relations(
  fileDependencies,
  ({ one }) => ({
    file_toFileId: one(files, {
      fields: [fileDependencies.toFileId],
      references: [files.id],
      relationName: "fileDependencies_toFileId_files_id",
    }),
    file_fromFileId: one(files, {
      fields: [fileDependencies.fromFileId],
      references: [files.id],
      relationName: "fileDependencies_fromFileId_files_id",
    }),
  }),
);

export const referencesRelations = relations(references, ({ one }) => ({
  definition_targetDefinitionId: one(definitions, {
    fields: [references.targetDefinitionId],
    references: [definitions.id],
    relationName: "references_targetDefinitionId_definitions_id",
  }),
  definition_sourceDefinitionId: one(definitions, {
    fields: [references.sourceDefinitionId],
    references: [definitions.id],
    relationName: "references_sourceDefinitionId_definitions_id",
  }),
}));

export const definitionDependenciesRelations = relations(
  definitionDependencies,
  ({ one }) => ({
    definition_toDefinitionId: one(definitions, {
      fields: [definitionDependencies.toDefinitionId],
      references: [definitions.id],
      relationName: "definitionDependencies_toDefinitionId_definitions_id",
    }),
    definition_fromDefinitionId: one(definitions, {
      fields: [definitionDependencies.fromDefinitionId],
      references: [definitions.id],
      relationName: "definitionDependencies_fromDefinitionId_definitions_id",
    }),
  }),
);
