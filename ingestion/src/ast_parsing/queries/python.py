"""
Python tree-sitter query definitions.

Patterns for:
- function definitions (incl. decorated)
- method definitions (functions inside classes)
- class definitions (incl. decorated)
- assignments that define callables via `lambda`
- simple variable assignments
"""

DECLARATION_PATTERN = """
[
  ;; ───────────── Functions (top-level) ─────────────────────────────────────
  (function_definition
    name: (identifier) @name_function) @def_function @def

  ;; If you want to tag async specifically, add this extra pattern:
  (function_definition
    "async" @kw_async
    name: (identifier) @name_function) @def_function @def

  ;; Decorated functions (incl. async)
  (decorated_definition
    (decorator)*
    definition: (function_definition
      name: (identifier) @name_function)) @def_function @def

  ;; name = lambda ...
  (expression_statement
    (assignment
      left:  (identifier) @name_function
      right: (lambda))) @def_function @def

  ;; bare lambda (anonymous)
  (lambda) @def_function @def

  ;; ───────────── Methods (inside class bodies) ─────────────────────────────
  (class_definition
    name: (identifier) @__class_placeholder
    (block
      (function_definition name: (identifier) @name_method) @def_method)) @def

  ;; decorated methods (incl. async) in class block
  (class_definition
    name: (identifier) @__class_placeholder
    (block
      (decorated_definition
        (decorator)*
        definition: (function_definition
          name: (identifier) @name_method)) @def_method)) @def

  ;; obj.attr = lambda ...  (treat like a method-style def)
  (expression_statement
    (assignment
      left: (attribute attribute: (identifier) @name_method)
      right: (lambda))) @def_method @def

  ;; ───────────── Classes ───────────────────────────────────────────────────
  (class_definition
    name: (identifier) @name_class) @def_class @def

  (decorated_definition
    (decorator)*
    definition: (class_definition
      name: (identifier) @name_class)) @def_class @def

  ;; ───────────── Variables / Constants (non-callable assignments) ─────────
  (expression_statement
    (assignment
      left: (identifier) @name_constant)) @def_constant @def
  (#match? @name_constant "^[A-Z_][A-Z0-9_]*$")

  (expression_statement
    (assignment
      left: (identifier) @name_variable)) @def_variable @def
]
"""

PYTHON_QUERY = f"""
; Pattern A: declaration WITH preceding line comments
(((comment) @doc)*
  .
  {DECLARATION_PATTERN})

; Pattern B: declaration WITHOUT preceding comments
({DECLARATION_PATTERN})
"""
