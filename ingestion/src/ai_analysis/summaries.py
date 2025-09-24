"""AI-powered summary generation for files and definitions.

This module implements recursive summary generation that respects dependency
orders and handles circular dependencies appropriately.
"""

import os
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from database.models import (
    DefinitionModel,
    FileModel,
)

# OpenAI client initialization
_openai_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create AsyncOpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        api_key = os.environ.get("SUMMARIES_API_KEY")
        _openai_client = AsyncOpenAI(
            api_key=api_key, base_url=os.getenv("SUMMARIES_BASE_URL") or None
        )
    return _openai_client


def _estimate_tokens(text: str) -> int:
    """Estimate number of tokens in text using 1 token = 3/4 words approximation.

    Args:
        text: Input text to analyze

    Returns:
        Estimated number of tokens
    """
    if not text:
        return 0

    # Simple word count (split by whitespace)
    word_count = len(text.split())

    # Apply 1 token = 3/4 words approximation
    return int(word_count * 4 / 3)


def _estimate_summary_tokens(entity_type: str) -> int:
    """Estimate tokens for generated summaries based on expected length.

    Args:
        entity_type: Type of entity ("file" or "definition")

    Returns:
        Estimated number of tokens for the summary
    """
    if entity_type == "file":
        # File summary: 8-10 sentences, ~15 words per sentence average
        return int(9 * 15 * 4 / 3)  # 180 tokens
    elif entity_type == "definition":
        # Definition summary: 2-4 sentences, ~15 words per sentence average
        return int(3 * 15 * 4 / 3)  # 60 tokens
    else:
        return 60  # Default to definition-like summary


def _calculate_file_input_tokens(file: FileModel, num_definitions: int) -> int:
    """Calculate estimated tokens for file summary input.

    File summary input = file content + summaries of all definitions in the file

    Args:
        file: FileModel instance
        num_definitions: Number of definitions in the file

    Returns:
        Estimated number of input tokens
    """
    file_content_tokens = _estimate_tokens(file.file_content or "")
    definition_summaries_tokens = num_definitions * _estimate_summary_tokens(
        "definition"
    )

    return file_content_tokens + definition_summaries_tokens


def _calculate_definition_input_tokens(
    definition: DefinitionModel, num_dependencies: int
) -> int:
    """Calculate estimated tokens for definition summary input.

    Definition summary input = definition source code + summaries of direct dependencies

    Args:
        definition: DefinitionModel instance
        num_dependencies: Number of direct dependencies (function calls + type references)

    Returns:
        Estimated number of input tokens
    """
    source_code_tokens = _estimate_tokens(definition.source_code or "")
    dependency_summaries_tokens = num_dependencies * _estimate_summary_tokens(
        "definition"
    )

    return source_code_tokens + dependency_summaries_tokens


# In-memory cache for single analysis run
file_summary_cache: dict[int, str] = {}
definition_summary_cache: dict[int, str] = {}

# Global token counters
function_input_tokens: int = 0
function_output_tokens: int = 0
file_input_tokens: int = 0
file_output_tokens: int = 0
summaries_generated: int = 0


def parse_llm_response(response: str) -> tuple[str, str]:
    """Parse the LLM response to extract the short and full summaries."""

    # short summary is between the <gist> </gist> tags
    short_summary = response.split("<gist>")[1].split("</gist>")[0]
    full_summary = response.split("</gist>")[1]

    return short_summary, full_summary


def clear_summary_caches() -> None:
    """Clear in-memory summary caches. Call this at the start of a new analysis run."""
    global file_summary_cache, definition_summary_cache
    global function_input_tokens, function_output_tokens
    global file_input_tokens, file_output_tokens
    global summaries_generated

    file_summary_cache.clear()
    definition_summary_cache.clear()

    # Reset token counters
    function_input_tokens = 0
    function_output_tokens = 0
    file_input_tokens = 0
    file_output_tokens = 0
    summaries_generated = 0


def get_file_prompt(file: FileModel) -> str:
    """Generate the prompt for file-level summary generation.

    Adds an ID catalog so the LLM can produce explicit citations that the
    web client converts into navigable links.
    """

    if not file.file_content:
        raise ValueError("File content is missing")

    # Build ID catalogs for citations
    definitions_catalog = "\n".join(
        [
            f" - def_id={d.id} | {d.definition_type} {d.name}"
            for d in (file.definitions or [])
        ]
    )

    # Gather connected files (both directions) if available
    connected_files: set[tuple[int, str]] = set()
    try:
        for dep in getattr(file, "file_dependencies", []) or []:  # from -> to
            if dep.to_file:
                connected_files.add((dep.to_file.id, dep.to_file.file_path))
        for dep in getattr(file, "file_dependents", []) or []:  # other -> this
            if dep.from_file:
                connected_files.add((dep.from_file.id, dep.from_file.file_path))
    except Exception:
        # Be resilient to lazy-loading/session edge cases
        pass

    connected_files_catalog = "\n".join(
        [f" - file_id={fid} | {fpath}" for fid, fpath in sorted(connected_files)]
    )

    # Definitions this file's symbols reference (may span other files)
    external_defs: set[tuple[int, int, str, str]] = set()
    try:
        for d in (file.definitions or []):
            for ref in getattr(d, "references", []) or []:
                if ref.target_definition:
                    external_defs.add(
                        (
                            ref.target_definition.id,
                            ref.target_definition.file.id,
                            ref.target_definition.definition_type,
                            ref.target_definition.name,
                        )
                    )
    except Exception:
        pass

    external_defs_catalog = "\n".join(
        [
            f" - dep_def_id={def_id} | {def_type} {def_name} (file_id={dep_file_id})"
            for (def_id, dep_file_id, def_type, def_name) in sorted(external_defs)
        ]
    )

    FILE_PROMPT = f"""
        # CONTEXT (verbatim; do NOT alter)
        FILE_ID: {file.id}
        FILE_PATH: {file.file_path}

        ## Raw Source
        ```typescript
        {file.file_content or "<no content>"}
        ```

        ## Pre‑generated Definition Summaries
        Each entry below describes a top‑level definition (function, class, interface, type alias, enum, constant, etc.) found in the file.  
        Use them to avoid repeating definition‑level detail and to determine the file's overall intent.

        {[f"{d.definition_type} '{d.name}': {d.ai_summary}\n\n" for d in file.definitions]}

        ## ID Catalog for Citations
        Use the following IDs to produce markdown links that cite files/definitions explicitly.
        - When you mention THIS file, you MAY cite it as: [short text](file::{file.id})
        - When you mention a definition from this file, cite it as: [Name](file::{file.id}:definition::{'{'}DEF_ID{'}'})
        - When you mention a CONNECTED file, cite it as: [short text](file::FILE_ID)
        - When you mention a referenced definition from the catalog below, cite it as: [Name](file::{'{'}DEP_FILE_ID{'}'}:definition::{'{'}DEP_DEF_ID{'}'})
        - Only cite items that appear in these catalogs. Do not invent IDs.

        ### Definitions in this file
        {definitions_catalog or "- <none>"}

        ### Connected files (imports/usage)
        {connected_files_catalog or "- <none>"}

        ### Referenced definitions (across files)
        {external_defs_catalog or "- <none>"}
    """

    return FILE_PROMPT


def get_definition_prompt(definition: DefinitionModel) -> str:
    """Generate the prompt for definition-level summary generation.

    Adds an ID catalog so the LLM can produce explicit citations that the
    web client converts into navigable links.
    """

    if not definition.source_code:
        raise ValueError("Definition source code is missing")

    # Build catalogs for citations
    # Direct dependencies (resolved references only)
    dep_catalog_lines: list[str] = []
    for ref in getattr(definition, "references", []) or []:
        if ref.target_definition:
            dep_catalog_lines.append(
                f" - dep_def_id={ref.target_definition.id} | {ref.target_definition.definition_type} {ref.target_definition.name} (file_id={ref.target_definition.file.id})"
            )
    dep_catalog = "\n".join(dep_catalog_lines)

    # Siblings in the same file (helpful for local citations)
    try:
        siblings_catalog = "\n".join(
            [
                f" - def_id={d.id} | {d.definition_type} {d.name}"
                for d in (definition.file.definitions or [])
                if d.id != definition.id
            ]
        )
    except Exception:
        siblings_catalog = ""

    DEFINITION_PROMPT = f"""
        # CONTEXT (verbatim; do NOT alter)
        FILE_ID: {definition.file.id}
        FILE_PATH: {definition.file.file_path}
        DEFINITION_ID: {definition.id}
        DEFINITION_NAME: {definition.name}
        DEFINITION_TYPE: {definition.definition_type}

        ## Raw Source
        ```typescript
        {definition.docstring or ""}
        {definition.source_code}
        ```

        ## Pre‑generated Dependency Summaries
        Each entry below describes a direct dependency (function call, type reference, etc.) used by this definition.  
        Use them to avoid repeating dependency‑level detail and to focus on the definition's purpose.

        {[f" - '{d.reference_name}': {d.target_definition.ai_summary}\n\n" for d in definition.references if d.target_definition]}

        ## ID Catalog for Citations
        Use the following IDs to produce markdown links that cite files/definitions explicitly.
        - When you mention THIS definition, you MAY cite it as: [short text](file::{definition.file.id}:definition::{definition.id})
        - When you mention another definition from the same file, cite it as: [Name](file::{definition.file.id}:definition::{'{'}DEF_ID{'}'})
        - When you mention a dependency below, cite it as: [Name](file::{'{'}DEP_FILE_ID{'}'}:definition::{'{'}DEP_DEF_ID{'}'})
        - Only cite items that appear in these catalogs. Do not invent IDs.

        ### Direct dependency IDs
        {dep_catalog or "- <none>"}

        ### Sibling definitions (same file)
        {siblings_catalog or "- <none>"}
    """

    return DEFINITION_PROMPT


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=120),
    retry=retry_if_exception_type((Exception,)),
)
async def generate_file_summary_with_llm(file: FileModel) -> tuple[str, str]:
    """Generate an AI summary for a file using OpenAI's GPT model.

    Args:
        file: FileModel instance

    Returns:
        AI-generated summary string
    """
    try:
        client = get_openai_client()

        response = await client.chat.completions.create(
            model=os.getenv("SUMMARIES_MODEL") or "google/gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": """
        # ROLE
        You are an expert technical writer with deep TypeScript knowledge who can explain code clearly to **beginners** while preserving details senior engineers care about.

        # TASKS
        1. **High‑level purpose (1-2 sentences).** What problem does this file solve?
        2. **Key exports.** List all *exported* symbols (default + named) with a one‑liner each describing their role.
        3. **Internal architecture.**
        • Explain how major definitions—including critical *non‑exported* helpers—collaborate.
        • Note call‑flow, data‑flow, notable algorithms, performance tricks, or side‑effects.
        4. **External dependencies.** Summarize imported packages / local modules (package name only) and *why* they’re needed.
        5. **Important implementation details.** Edge‑cases handled, assumptions made, error‑handling strategy, etc.
        6. **Usage guidance (optional if obvious).** One or two sentences on how downstream code should consume this module or what guarantees it exposes.

        # CITATIONS
        • When you mention a file or definition that appears in the provided ID Catalog, include a markdown link whose URL is one of:
          - `file::FILE_ID`
          - `file::FILE_ID:definition::DEF_ID`
        • Use a short, human‑readable link text (e.g., definition name or filename).
        • Do not invent IDs; only cite items present in the catalog.

        # STYLE GUIDELINES
        • **Stay under 200 words** unless the file is unusually complex.
        • Write for a junior developer first; use plain language but keep technical accuracy.
        • Prefer short paragraphs or bullet points; avoid code blocks unless essential.
        • Do not repeat the individual definition summaries verbatim—synthesize instead.
        • Use present tense and active voice.

        # OUTPUT FORMAT
        Return **plain markdown** with this format:

        <gist>
        1-2 line summary of the file
        </gist>

        ### Summary

        <high‑level purpose>

        ### Exports

        - `name`: <one‑liner description>
            …

        ### Architecture & Key Points

        ### Dependencies

        - `package-or-file`: why it's needed <one‑liner>
            …

        ### Usage Notes
        <optional guidance>
                            """,
                },
                {"role": "user", "content": get_file_prompt(file)},
            ],
            temperature=0.3,
            extra_body={
                "extra_body": {
                    "google": {
                        "thinking_config": {
                            "thinking_budget": 0,
                        }
                    }
                }
            },
        )

        global summaries_generated
        summaries_generated += 1

        content = response.choices[0].message.content
        if content:
            short_summary, full_summary = parse_llm_response(content)
            return short_summary, full_summary
        else:
            return "", ""

        # return (
        #     f"AI summary for file '{file.file_path}'",
        #     f"AI summary for file '{file.file_path}'",
        # )

    except Exception as e:
        print(f"  ❌ OpenAI API error for file '{file.file_path}': {e}")
        raise


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=120),
    retry=retry_if_exception_type((Exception,)),
)
async def generate_definition_summary_with_llm(
    definition: DefinitionModel,
) -> tuple[str, str]:
    """Generate an AI summary for a definition using OpenAI's GPT model.

    Args:
        definition: DefinitionModel instance

    Returns:
        AI-generated summary string
    """
    try:
        client = get_openai_client()

        if definition.definition_type == "function":
            property_details = """
            Parameters & Return
             - param `name`: <one‑liner description>
                …
            """
        elif definition.definition_type in ["class", "interface"]:
            property_details = """
                                Properties
                                - property `name`: <one‑liner description>
                                """
        else:
            property_details = "Details"

        response = await client.chat.completions.create(
            model=os.getenv("SUMMARIES_MODEL") or "google/gemini-2.5-flash",
            messages=[
                {
                    "role": "system",
                    "content": f"""
        # ROLE
        You are an experienced TypeScript engineer and technical writer.
        You must produce a **beginner‑friendly yet detail‑rich summary** of a single definition so junior developers can grasp it quickly, while senior devs still find the nuances they need.

        # TASKS
        1. **Purpose (1–2 sentences).** What does this definition do or represent?
        2. **Parameters & returns** (if applicable).
           • Describe each parameter’s role, expected shape, and important validation.
           • Explain the return value and any side‑effects (I/O, mutations, state).
        3. **Key logic & algorithm highlights.** Mention tricky branches, loops, performance considerations, or error handling.
        4. **Dependencies explained.** For each item in the dependency map that truly matters, explain *why* it’s used – keep it concise.
        5. **Usage guidance (optional if obvious).** How should callers use this symbol safely? Any caveats?
        6. **Edge‑cases & assumptions.** List notable constraints, default values, or failure modes.

        # CITATIONS
        • When you mention this definition, any sibling definitions, or direct dependencies listed in the ID Catalog, include a markdown link whose URL is one of:
          - `file::{'{'}FILE_ID{'}'}:definition::{'{'}DEF_ID{'}'}` (for definitions)
          - `file::{'{'}FILE_ID{'}'}` (for files when appropriate)
        • Use the human‑readable name as link text.
        • Do not invent IDs; only cite items present in the catalog.

        # STYLE GUIDELINES
        • **Target ≤ 120 words** unless the definition is complex.
        • Use plain language, short sentences, and active voice.
        • Bullets are fine; avoid code blocks unless a tiny snippet clarifies a tricky algorithm.
        • Reference dependencies by name, not full import paths.
        • Do **not** restate the raw code. Summarize and explain instead.

        # IMPORTANT
        • If the definition is simple, keep the summary concise. You do not need to include any unnecessary details.

        # OUTPUT FORMAT
        Return **plain markdown** with this format:

        <gist>
        1-2 line summary of the definition
        </gist>

        ### Summary
        <high‑level purpose>

        ### {property_details}

        ### Key Points
        <optional: bullets or short paragraph>

        ### Dependencies
        <optional: if any dependencies are used>

        - `dependency`: why it's needed <one‑liner>
            …

        ### Usage Notes
        <optional: guidance on how to use this definition>
                            """,
                },
                {"role": "user", "content": get_definition_prompt(definition)},
            ],
            temperature=0.3,
            extra_body={
                "extra_body": {
                    "google": {
                        "thinking_config": {
                            "thinking_budget": 0,
                        }
                    }
                }
            },
        )

        content = response.choices[0].message.content
        global summaries_generated
        summaries_generated += 1
        if content:
            short_summary, full_summary = parse_llm_response(content)
            return short_summary, full_summary
        else:
            return "", ""

        # print(f"definition summary system prompt:\n\n {get_definition_prompt(definition)}")

        # return (
        #     f"[AI_SUCCESS] Summary for definition '{definition.name}'",
        #     "[AI_SUCCESS] Summary for definition '{definition.name}'",
        # )

    except Exception as e:
        print(
            f"  ❌ OpenAI API error for {definition.definition_type} '{definition.name}': {e}"
        )
        raise


def _generate_placeholder_summary(content: str, entity_type: str, name: str) -> str:
    """Generate a placeholder summary from source code content (fallback only).

    Args:
        content: Source code content
        entity_type: Type of entity (file, function, class, etc.)
        name: Name of the entity

    Returns:
        Placeholder summary string
    """
    # Show first 100 characters of content for debugging
    preview = content[:100].replace("\n", " ").strip() if content else "<no content>"
    return f"[PLACEHOLDER] {entity_type} '{name}': {preview}..."


def get_token_summary() -> dict[str, int]:
    """Get summary of total token usage.

    Returns:
        Dictionary with token usage statistics
    """
    global \
        file_input_tokens, \
        file_output_tokens, \
        function_input_tokens, \
        function_output_tokens, \
        summaries_generated

    return {
        "total_file_input_tokens": file_input_tokens,
        "total_file_output_tokens": file_output_tokens,
        "total_file_tokens": file_input_tokens + file_output_tokens,
        "total_function_input_tokens": function_input_tokens,
        "total_function_output_tokens": function_output_tokens,
        "total_function_tokens": function_input_tokens + function_output_tokens,
        "file_summaries_generated": summaries_generated,
        "definition_summaries_generated": summaries_generated,
        "average_input_tokens_per_file": file_input_tokens // summaries_generated
        if summaries_generated > 0
        else 0,
        "average_input_tokens_per_definition": function_input_tokens
        // summaries_generated
        if summaries_generated > 0
        else 0,
    }
