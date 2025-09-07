-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TABLE `files` (
	`id` integer PRIMARY KEY NOT NULL,
	`file_path` text NOT NULL,
	`file_content` text NOT NULL,
	`language` text NOT NULL,
	`last_modified` numeric NOT NULL,
	`created_at` numeric NOT NULL,
	`updated_at` numeric NOT NULL,
	`ai_summary` text,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_files_path` ON `files` (`file_path`);--> statement-breakpoint
CREATE INDEX `idx_files_language` ON `files` (`language`);--> statement-breakpoint
CREATE TABLE `packages` (
	`id` integer PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`path` text NOT NULL,
	`entry_point` text,
	`workspace_type` text,
	`is_workspace_root` numeric NOT NULL,
	`created_at` numeric NOT NULL,
	`updated_at` numeric NOT NULL,
	`readme_content` text,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_packages_workspace_root` ON `packages` (`is_workspace_root`);--> statement-breakpoint
CREATE INDEX `idx_packages_path` ON `packages` (`path`);--> statement-breakpoint
CREATE INDEX `idx_packages_name` ON `packages` (`name`);--> statement-breakpoint
CREATE TABLE `definitions` (
	`created_at` numeric NOT NULL,
	`id` integer PRIMARY KEY NOT NULL,
	`file_id` integer NOT NULL,
	`name` text NOT NULL,
	`definition_type` text NOT NULL,
	`start_line` integer NOT NULL,
	`end_line` integer NOT NULL,
	`docstring` text,
	`source_code` text,
	`source_code_hash` text,
	`is_exported` numeric NOT NULL,
	`is_default_export` numeric NOT NULL,
	`complexity_score` integer,
	`ai_summary` text,
	FOREIGN KEY (`file_id`) REFERENCES `files`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_definitions_file_type` ON `definitions` (`file_id`,`definition_type`);--> statement-breakpoint
CREATE INDEX `idx_definitions_name` ON `definitions` (`name`);--> statement-breakpoint
CREATE INDEX `idx_definitions_exported` ON `definitions` (`is_exported`);--> statement-breakpoint
CREATE INDEX `idx_definitions_source_code_hash` ON `definitions` (`source_code_hash`);--> statement-breakpoint
CREATE TABLE `imports` (
	`id` integer PRIMARY KEY NOT NULL,
	`file_id` integer NOT NULL,
	`specifier` text NOT NULL,
	`module` text NOT NULL,
	`import_type` text NOT NULL,
	`resolved_file_path` text,
	`alias` text,
	`is_external` numeric NOT NULL,
	`target_package_id` integer,
	`resolution_type` text,
	FOREIGN KEY (`target_package_id`) REFERENCES `packages`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`file_id`) REFERENCES `files`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_imports_file` ON `imports` (`file_id`);--> statement-breakpoint
CREATE INDEX `idx_imports_resolution_type` ON `imports` (`resolution_type`);--> statement-breakpoint
CREATE INDEX `idx_imports_target_package` ON `imports` (`target_package_id`);--> statement-breakpoint
CREATE INDEX `idx_imports_module` ON `imports` (`module`);--> statement-breakpoint
CREATE TABLE `file_dependencies` (
	`id` integer PRIMARY KEY NOT NULL,
	`from_file_id` integer NOT NULL,
	`to_file_id` integer NOT NULL,
	FOREIGN KEY (`to_file_id`) REFERENCES `files`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`from_file_id`) REFERENCES `files`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_file_dependencies_to` ON `file_dependencies` (`to_file_id`);--> statement-breakpoint
CREATE INDEX `idx_file_dependencies_from` ON `file_dependencies` (`from_file_id`);--> statement-breakpoint
CREATE TABLE `type_references` (
	`id` integer PRIMARY KEY NOT NULL,
	`definition_id` integer NOT NULL,
	`type_name` text NOT NULL,
	`source` text NOT NULL,
	`source_definition_id` integer,
	`import_id` integer,
	FOREIGN KEY (`import_id`) REFERENCES `imports`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`source_definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_type_references_definition` ON `type_references` (`definition_id`);--> statement-breakpoint
CREATE INDEX `idx_type_references_source` ON `type_references` (`source_definition_id`);--> statement-breakpoint
CREATE TABLE `function_calls` (
	`id` integer PRIMARY KEY NOT NULL,
	`callee_name` text NOT NULL,
	`callee_source` text,
	`caller_definition_id` integer NOT NULL,
	`callee_definition_id` integer,
	`import_id` integer,
	FOREIGN KEY (`import_id`) REFERENCES `imports`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`callee_definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE set null,
	FOREIGN KEY (`caller_definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_function_calls_callee` ON `function_calls` (`callee_definition_id`);--> statement-breakpoint
CREATE INDEX `idx_function_calls_caller` ON `function_calls` (`caller_definition_id`);--> statement-breakpoint
CREATE TABLE `definition_dependencies` (
	`created_at` numeric NOT NULL,
	`id` integer PRIMARY KEY NOT NULL,
	`from_definition_id` integer NOT NULL,
	`to_definition_id` integer NOT NULL,
	`dependency_type` text NOT NULL,
	`strength` integer NOT NULL,
	FOREIGN KEY (`to_definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE cascade,
	FOREIGN KEY (`from_definition_id`) REFERENCES `definitions`(`id`) ON UPDATE no action ON DELETE cascade,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `idx_dependencies_type` ON `definition_dependencies` (`dependency_type`);--> statement-breakpoint
CREATE INDEX `idx_dependencies_dependent` ON `definition_dependencies` (`from_definition_id`);--> statement-breakpoint
CREATE INDEX `idx_dependencies_dependency` ON `definition_dependencies` (`to_definition_id`);--> statement-breakpoint
CREATE TABLE `embeddings` (
	`id` integer PRIMARY KEY NOT NULL,
	`entity_type` text NOT NULL,
	`entity_id` integer NOT NULL,
	`entity_name` text,
	`file_path` text,
	`language` text,
	`definition_type` text,
	`is_exported` integer,
	`complexity_score` integer,
	`created_at` text DEFAULT 'datetime(''now'')' NOT NULL,
	`embedding` numeric NOT NULL,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `embeddings_idx` ON `embeddings` (``);--> statement-breakpoint
CREATE UNIQUE INDEX `embeddings_entity_unique` ON `embeddings` (`entity_type`,`entity_id`);--> statement-breakpoint
CREATE TABLE `embeddings_idx_shadow` (
	`index_key` integer PRIMARY KEY,
	`data` blob,
	CONSTRAINT "definitions_check_1" CHECK(definition_type IN ('function', 'class', 'interface', 'type', 'variable', 'constructor', 'enum', 'module'),
	CONSTRAINT "imports_check_2" CHECK(import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export'),
	CONSTRAINT "imports_check_3" CHECK(resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown'),
	CONSTRAINT "type_references_check_4" CHECK(source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "function_calls_check_5" CHECK(callee_source IN ('local', 'imported', 'unknown'),
	CONSTRAINT "definition_dependencies_check_6" CHECK(dependency_type IN ('type_reference', 'function_call', 'inheritance', 'import'),
	CONSTRAINT "embeddings_check_7" CHECK(entity_type in ('file','definition')
);
--> statement-breakpoint
CREATE INDEX `embeddings_idx_shadow_idx` ON `embeddings_idx_shadow` (`index_key`);
*/