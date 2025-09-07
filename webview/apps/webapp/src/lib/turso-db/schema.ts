import { sql } from "drizzle-orm";
import {
  check,
  index,
  integer,
  numeric,
  sqliteTable,
  text,
} from "drizzle-orm/sqlite-core";

export const repositories = sqliteTable(
  "repositories",
  {
    id: integer().primaryKey().notNull(),
    remoteOriginUrl: text("remote_origin_url").notNull(),
    commitHash: text("commit_hash"),
    defaultBranch: text("default_branch"),
  },
  (table) => [
    index("idx_repositories_remote_origin_url").on(table.remoteOriginUrl),
    index("idx_repositories_commit").on(table.commitHash),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const packages = sqliteTable(
  "packages",
  {
    id: integer().primaryKey().notNull(),
    repositoryId: integer("repository_id")
      .notNull()
      .references(() => repositories.id, { onDelete: "cascade" }),
    name: text().notNull(),
    path: text().notNull(),
    entryPoint: text("entry_point"),
    workspaceType: text("workspace_type"),
    isWorkspaceRoot: numeric("is_workspace_root").notNull(),
    createdAt: numeric("created_at").notNull(),
    updatedAt: numeric("updated_at").notNull(),
    readmeContent: text("readme_content"),
  },
  (table) => [
    index("idx_packages_repository").on(table.repositoryId),
    index("idx_packages_workspace_root").on(table.isWorkspaceRoot),
    index("idx_packages_path").on(table.path),
    index("idx_packages_name").on(table.name),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const files = sqliteTable(
  "files",
  {
    id: integer().primaryKey().notNull(),
    packageId: integer("package_id").references(() => packages.id, {
      onDelete: "set null",
    }),
    filePath: text("file_path").notNull(),
    fileContent: text("file_content").notNull(),
    language: text().notNull(),
    lastModified: numeric("last_modified").notNull(),
    createdAt: numeric("created_at").notNull(),
    updatedAt: numeric("updated_at").notNull(),
    aiSummary: text("ai_summary"),
    aiShortSummary: text("ai_short_summary"),
  },
  (table) => [
    index("idx_files_language").on(table.language),
    index("idx_files_path").on(table.filePath),
    index("idx_files_package").on(table.packageId),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const definitions = sqliteTable(
  "definitions",
  {
    createdAt: numeric("created_at").notNull(),
    id: integer().primaryKey().notNull(),
    fileId: integer("file_id")
      .notNull()
      .references(() => files.id, { onDelete: "cascade" }),
    name: text().notNull(),
    definitionType: text("definition_type").notNull(),
    startLine: integer("start_line").notNull(),
    endLine: integer("end_line").notNull(),
    docstring: text(),
    sourceCode: text("source_code"),
    sourceCodeHash: text("source_code_hash"),
    isExported: numeric("is_exported").notNull(),
    isDefaultExport: numeric("is_default_export").notNull(),
    complexityScore: integer("complexity_score"),
    aiSummary: text("ai_summary"),
    aiShortSummary: text("ai_short_summary"),
  },
  (table) => [
    index("idx_definitions_name").on(table.name),
    index("idx_definitions_file_type").on(table.fileId, table.definitionType),
    index("idx_definitions_source_code_hash").on(table.sourceCodeHash),
    index("idx_definitions_exported").on(table.isExported),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const imports = sqliteTable(
  "imports",
  {
    id: integer().primaryKey().notNull(),
    fileId: integer("file_id")
      .notNull()
      .references(() => files.id, { onDelete: "cascade" }),
    specifier: text().notNull(),
    module: text().notNull(),
    importType: text("import_type").notNull(),
    resolvedFilePath: text("resolved_file_path"),
    alias: text(),
    isExternal: numeric("is_external").notNull(),
    targetPackageId: integer("target_package_id").references(
      () => packages.id,
      {
        onDelete: "set null",
      },
    ),
    resolutionType: text("resolution_type"),
  },
  (table) => [
    index("idx_imports_module").on(table.module),
    index("idx_imports_resolution_type").on(table.resolutionType),
    index("idx_imports_target_package").on(table.targetPackageId),
    index("idx_imports_file").on(table.fileId),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const fileDependencies = sqliteTable(
  "file_dependencies",
  {
    id: integer().primaryKey().notNull(),
    fromFileId: integer("from_file_id")
      .notNull()
      .references(() => files.id, { onDelete: "cascade" }),
    toFileId: integer("to_file_id")
      .notNull()
      .references(() => files.id, { onDelete: "cascade" }),
  },
  (table) => [
    index("idx_file_dependencies_from").on(table.fromFileId),
    index("idx_file_dependencies_to").on(table.toFileId),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const references = sqliteTable(
  "references",
  {
    id: integer().primaryKey().notNull(),
    referenceName: text("reference_name").notNull(),
    referenceType: text("reference_type"),
    sourceDefinitionId: integer("source_definition_id")
      .notNull()
      .references(() => definitions.id, { onDelete: "cascade" }),
    targetDefinitionId: integer("target_definition_id").references(
      () => definitions.id,
      {
        onDelete: "set null",
      },
    ),
  },
  (table) => [
    index("idx_references_source").on(table.sourceDefinitionId),
    index("idx_references_target").on(table.targetDefinitionId),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);

export const definitionDependencies = sqliteTable(
  "definition_dependencies",
  {
    createdAt: numeric("created_at").notNull(),
    id: integer().primaryKey().notNull(),
    fromDefinitionId: integer("from_definition_id")
      .notNull()
      .references(() => definitions.id, { onDelete: "cascade" }),
    toDefinitionId: integer("to_definition_id")
      .notNull()
      .references(() => definitions.id, { onDelete: "cascade" }),
    dependencyType: text("dependency_type").notNull(),
    strength: integer().notNull(),
  },
  (table) => [
    index("idx_dependencies_dependency").on(table.toDefinitionId),
    index("idx_dependencies_dependent").on(table.fromDefinitionId),
    index("idx_dependencies_type").on(table.dependencyType),
    check(
      "definitions_check_1",
      sql`definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'`,
    ),
    check(
      "imports_check_2",
      sql`import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'`,
    ),
    check(
      "imports_check_3",
      sql`resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'`,
    ),
    check(
      "references_check_4",
      sql`reference_type IN ('local', 'imported', 'unknown'`,
    ),
    check(
      "definition_dependencies_check_5",
      sql`dependency_type IN ('reference', 'inheritence', 'import'`,
    ),
  ],
);
