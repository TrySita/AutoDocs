"""
TypeScript tree-sitter query definitions.

Patterns for:
- function signatures and declarations
- method signatures and definitions
- abstract method signatures
- class declarations (including abstract classes)
- module declarations
- exported variable declarations with arrow functions
- exported const declarations
"""

DECLARATION_PATTERN_TYPED = """
[
  ;; ───── Functions (named) ────────────────────────────────────────────────
  (function_declaration
    name: (identifier) @name_function) @def_function @def

  ;; Function signatures (TS type-level)
  (function_signature
    name: (identifier) @name_function) @def_function @def

  ;; const/let/var f = () => {} | function () {}
  (variable_declarator
    name: (identifier) @name_function
    value: [(arrow_function) (function_expression)]) @def_function @def

  ;; id = () => {} | id = function() {} | id = function_signature
  (expression_statement
    (assignment_expression
      left:  (identifier) @name_function
      right: [(function_signature) (function_expression) (arrow_function)])) @def_function @def

  ;; Anonymous arrow function (no name)
  (arrow_function) @def_function @def

  ;; ───── Methods (class/interface/object-style) ───────────────────────────
  (method_definition              name: (property_identifier) @name_method) @def_method @def
  (method_signature               name: (property_identifier) @name_method) @def_method @def
  (abstract_method_signature      name: (property_identifier) @name_method) @def_method @def

  ;; obj.prop = () => {} | obj.prop = function() {}
  (expression_statement
    (assignment_expression
      left: (member_expression
              property: (property_identifier) @name_method)
      right: [(function_expression) (arrow_function)])) @def_method @def

  ;; ───── Classes ─────────────────────────────────────────────────────────
  (class_declaration              name: (type_identifier)     @name_class)      @def_class @def
  (abstract_class_declaration     name: (type_identifier)     @name_class)      @def_class @def

  ;; ───── Interfaces / Types / Enums / Modules ────────────────────────────
  (interface_declaration          name: (type_identifier)     @name_interface)  @def_interface @def
  (type_alias_declaration         name: (type_identifier)     @name_type_alias) @def_type_alias @def
  (enum_declaration               name: (identifier)          @name_enum)       @def_enum @def
  (module                         name: (identifier)          @name_module)     @def_module @def

  ;; ───── Exported function values ────────────────────────────────────────
  (export_statement
    (lexical_declaration
      (variable_declarator
        name: (identifier) @name_function
        value: [(arrow_function) (function_expression)]))) @def_function @def

  (export_statement
    (variable_declaration
      (variable_declarator
        name: (identifier) @name_function
        value: [(arrow_function) (function_expression)]))) @def_function @def

  ;; ───── Constants / Variables (non-function values) ─────────────────────
  ;; const NAME = <non-function>
  (lexical_declaration
    "const"
    (variable_declarator
      name: (identifier) @name_constant)) @def_constant @def

  (export_statement
    (lexical_declaration
      "const"
      (variable_declarator
        name: (identifier) @name_constant))) @def_constant @def

  ;; let NAME = <non-function>
  (lexical_declaration
    "let"
    (variable_declarator
      name: (identifier) @name_variable)) @def_variable @def

  ;; var NAME = <non-function>
  (variable_declaration
    (variable_declarator
      name: (identifier) @name_variable)) @def_variable @def
]
"""


TYPESCRIPT_QUERY = f"""
;; Pattern A: JSDoc immediately above a declaration
((comment)* @doc
  .
  {DECLARATION_PATTERN_TYPED})

;; Pattern B: declaration without JSDoc
({DECLARATION_PATTERN_TYPED})
"""
