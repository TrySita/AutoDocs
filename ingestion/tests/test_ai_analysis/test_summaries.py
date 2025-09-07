"""Unit tests for AI analysis summary functions."""

import pytest
from ai_analysis.summaries import parse_llm_response


class TestParseLLMResponse:
    """Test the parse_llm_response function."""

    def test_parse_normal_response(self):
        """Test parsing a well-formed LLM response with gist and full summary."""
        response = """<gist>
This is a short summary of the file.
</gist>

### Summary
This is the full detailed summary of the file.
It contains multiple paragraphs and sections.
"""
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == "\nThis is a short summary of the file.\n"
        assert full_summary == "\n\n### Summary\nThis is the full detailed summary of the file.\nIt contains multiple paragraphs and sections.\n"

    def test_parse_minimal_response(self):
        """Test parsing a minimal response with just the gist tags."""
        response = "<gist>Short summary</gist>Full summary"
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == "Short summary"
        assert full_summary == "Full summary"

    def test_parse_empty_gist(self):
        """Test parsing response with empty gist content."""
        response = "<gist></gist>Full summary content"
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == ""
        assert full_summary == "Full summary content"

    def test_parse_multiline_gist(self):
        """Test parsing response with multiline gist content."""
        response = """<gist>
Line 1 of gist
Line 2 of gist
</gist>
Full summary starts here"""
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == "\nLine 1 of gist\nLine 2 of gist\n"
        assert full_summary == "\nFull summary starts here"

    def test_parse_no_gist_tags(self):
        """Test parsing response without gist tags (should raise IndexError)."""
        response = "This is just a regular response without tags"

        with pytest.raises(IndexError):
            parse_llm_response(response)

    def test_parse_missing_closing_gist_tag(self):
        """Test parsing response with missing closing gist tag."""
        response = "<gist>Short summaryFull summary"

        with pytest.raises(IndexError):
            parse_llm_response(response)

    def test_parse_empty_response(self):
        """Test parsing empty response string."""
        response = ""

        with pytest.raises(IndexError):
            parse_llm_response(response)

    def test_parse_only_gist_no_content_after(self):
        """Test parsing response with only gist content and no content after."""
        response = "<gist>Only gist content</gist>"
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == "Only gist content"
        assert full_summary == ""

    def test_parse_with_whitespace_around_tags(self):
        """Test parsing response with whitespace around gist tags."""
        response = "  <gist>  Short summary  </gist>  Full summary  "
        short_summary, full_summary = parse_llm_response(response)

        assert short_summary == "  Short summary  "
        assert full_summary == "  Full summary  "

    def test_parse_complex_markdown_response(self):
        """Test parsing a complex markdown response similar to actual LLM output."""
        response = """<gist>
Utility functions for file operations and path handling
</gist>

### Summary

This module provides essential utility functions for file system operations and path manipulation in the analysis agent.

### Exports

- `read_file_content`: Reads and returns the content of a file at the specified path
- `get_file_extension`: Extracts the file extension from a given file path
- `normalize_path`: Converts relative paths to absolute paths

### Architecture & Key Points

The module follows a simple functional approach with pure functions that don't maintain state. All functions include proper error handling for file operations.

### Dependencies

- `os`: Standard library for file system operations
- `pathlib`: Modern path handling utilities

### Usage Notes
These utilities are designed to be used throughout the codebase for consistent file handling."""
        short_summary, full_summary = parse_llm_response(response)

        assert "Utility functions for file operations" in short_summary
        assert "### Summary" in full_summary
        assert "### Exports" in full_summary
        assert "### Dependencies" in full_summary