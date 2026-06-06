"""
JavaScript tree-sitter query definitions.

Patterns for:
- function declarations
- function/arrow initializers in variable declarators
- assignment of functions/arrows to identifiers and object properties
- method definitions
- class declarations
- exported variable declarations with arrow functions or function expressions
- plain variable declarations (const/let/var)

Captures are typed (``@def_<kind>``/``@name_<kind>``) so the parser's
kind-aware extraction loop in ``parser.py`` can resolve each match, mirroring
the structure of ``typescript.py``. JavaScript has no interfaces, type
aliases, enums, or modules, so only function/method/class/constant/variable
kinds appear here.
"""

DECLARATION_PATTERN_JS = """
[
  ;; ───── Functions (named) ────────────────────────────────────────────────
  ;; function name() {…}
  (function_declaration
    name: (identifier) @name_function) @def_function @def

  ;; const/let/var name = () => {} | function () {}
  (variable_declarator
    name: (identifier) @name_function
    value: [(arrow_function) (function_expression)]) @def_function @def

  ;; name = function() {} | name = () => {}
  (expression_statement
    (assignment_expression
      left:  (identifier) @name_function
      right: [(function_expression) (arrow_function)])) @def_function @def

  ;; Anonymous arrow function (no name)
  (arrow_function) @def_function @def

  ;; ───── Methods (class/object-style) ─────────────────────────────────────
  (method_definition              name: (property_identifier) @name_method) @def_method @def

  ;; obj.prop = function() {} | obj.prop = () => {} | obj.nested.prop = …
  (expression_statement
    (assignment_expression
      left: (member_expression
              property: (property_identifier) @name_method)
      right: [(function_expression) (arrow_function)])) @def_method @def

  ;; ───── Classes ──────────────────────────────────────────────────────────
  (class_declaration              name: (identifier)          @name_class) @def_class @def

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

JAVASCRIPT_QUERY = f"""
;; ───── Pattern A: declaration WITH a comment right above it ────────────────
((comment)* @doc
  .
  {DECLARATION_PATTERN_JS})

;; ───── Pattern B: declaration WITHOUT a comment ────────────────────────────
({DECLARATION_PATTERN_JS})
"""
