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
"""

DECLARATION_PATTERN_JS = """
[
  ;; 1. Variable declarator with function/arrow initializer → const name = () => {}, let name = function() {}
  (variable_declarator
    name: (identifier)        @name
    value: [(arrow_function) (function_expression)])           @def

  ;; 2. Assignment to identifier → name = function() {}, name = () => {}
  (expression_statement
    (assignment_expression
      left:  (identifier) @name
      right: [(function_expression) (arrow_function)]))        @def

  ;; 3. Assignment to object property → obj.prop = function() {}, obj.prop = () => {}, obj.nested.prop = function() {}
  (expression_statement
    (assignment_expression
      left: (member_expression
        property: (property_identifier) @name)
      right: [(function_expression) (arrow_function)]))        @def

  ;; 4. Arrow or async arrow → (x) => x ,  async (x) => {…}
  (arrow_function)                                              @def

  ;; 5. Function declaration → function name() {…}
  (function_declaration           name: (identifier)          @name) @def

  ;; 6. Method definition in classes/objects
  (method_definition              name: (property_identifier) @name) @def

  ;; 7. Class declaration
  (class_declaration              name: (identifier)          @name) @def

  ;; 8. export const/let/var name = () => {} | function() {}
  (export_statement
    (lexical_declaration
      (variable_declarator
        name: (identifier)        @name
        value: [(arrow_function) (function_expression)])))     @def

  (export_statement
    (variable_declaration
      (variable_declarator
        name: (identifier)        @name
        value: [(arrow_function) (function_expression)])))     @def

  ;; 9. Plain variable declarations (no initializer required)
  (lexical_declaration
    (variable_declarator
      name: (identifier)        @name))                        @def
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
