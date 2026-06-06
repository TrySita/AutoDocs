"""Regression tests for ai_analysis.summaries bug fixes (bugs 13, 20, 23, 26).

These tests are self-contained: they do not hit the network or require API
keys. The OpenAI client is replaced with an in-memory fake.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from openai import APIConnectionError, APITimeoutError, RateLimitError
from tenacity import RetryCallState

from ai_analysis import summaries


# --------------------------------------------------------------------------- #
# Bug 13: parse_llm_response must degrade gracefully on malformed output.
# --------------------------------------------------------------------------- #


class TestParseLLMResponseDefensive:
    """parse_llm_response should never raise on malformed model output."""

    def test_no_gist_tags_returns_whole_response_as_full(self) -> None:
        response = "This is just a regular response without tags"

        short_summary, full_summary = summaries.parse_llm_response(response)

        assert short_summary == ""
        assert full_summary == response

    def test_missing_closing_gist_tag_does_not_raise(self) -> None:
        response = "<gist>Short summaryFull summary"

        short_summary, full_summary = summaries.parse_llm_response(response)

        # No closing tag: gist content cannot be isolated, so keep the text as
        # the full summary rather than crashing the whole summary phase.
        assert short_summary == ""
        assert full_summary == response

    def test_empty_response_does_not_raise(self) -> None:
        short_summary, full_summary = summaries.parse_llm_response("")

        assert short_summary == ""
        assert full_summary == ""

    def test_well_formed_response_still_parses(self) -> None:
        response = "<gist>Short summary</gist>Full summary"

        short_summary, full_summary = summaries.parse_llm_response(response)

        assert short_summary == "Short summary"
        assert full_summary == "Full summary"


# --------------------------------------------------------------------------- #
# Shared fakes for the LLM-call tests (bugs 20, 23, 26).
# --------------------------------------------------------------------------- #


def _make_file(language: str = "python") -> Any:
    """Build a minimal FileModel-like object for prompt/summary tests."""
    return SimpleNamespace(
        id=1,
        file_path="src/example.py",
        file_content="def foo():\n    return 1\n",
        language=language,
        definitions=[],
        file_dependencies=[],
        file_dependents=[],
    )


def _make_definition(language: str = "python") -> Any:
    """Build a minimal DefinitionModel-like object for prompt/summary tests."""
    file = SimpleNamespace(
        id=1,
        file_path="src/example.py",
        language=language,
        definitions=[],
    )
    definition = SimpleNamespace(
        id=10,
        name="foo",
        definition_type="function",
        source_code="def foo():\n    return 1\n",
        docstring="",
        file=file,
        references=[],
    )
    file.definitions = [definition]
    return definition


class _FakeChatResponse:
    """Mimic the subset of the OpenAI chat-completions response we read."""

    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int) -> None:
        self.choices = [
            SimpleNamespace(message=SimpleNamespace(content=content)),
        ]
        self.usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )


class _FakeClient:
    """Captures the messages sent and returns a canned response."""

    def __init__(self, response: _FakeChatResponse) -> None:
        self._response = response
        self.captured_messages: list[dict[str, Any]] = []

        async def _create(**kwargs: Any) -> _FakeChatResponse:
            self.captured_messages = kwargs["messages"]
            return self._response

        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=_create),
        )


# --------------------------------------------------------------------------- #
# Bug 23: prompts must reflect the file's actual language, not hardcoded TS.
# --------------------------------------------------------------------------- #


class TestLanguageInPrompts:
    """The language must flow through to the prompt builders and system prompt."""

    def test_file_prompt_uses_file_language_fence(self) -> None:
        file = _make_file(language="python")

        prompt = summaries.get_file_prompt(file)

        assert "```python" in prompt
        assert "```typescript" not in prompt

    def test_definition_prompt_uses_file_language_fence(self) -> None:
        definition = _make_definition(language="python")

        prompt = summaries.get_definition_prompt(definition)

        assert "```python" in prompt
        assert "```typescript" not in prompt

    @pytest.mark.asyncio
    async def test_file_system_prompt_mentions_python_not_typescript(self) -> None:
        file = _make_file(language="python")
        client = _FakeClient(_FakeChatResponse("<gist>g</gist>full", 5, 7))

        summaries.clear_summary_caches()
        with patch.object(summaries, "get_openai_client", return_value=client):
            await summaries.generate_file_summary_with_llm(file)

        system_prompt = client.captured_messages[0]["content"]
        assert "TypeScript" not in system_prompt
        assert "Python" in system_prompt


# --------------------------------------------------------------------------- #
# Bug 26: token counters must reflect real usage from response.usage.
# --------------------------------------------------------------------------- #


class TestTokenAccounting:
    """get_token_summary must report real, separated token usage."""

    @pytest.mark.asyncio
    async def test_file_and_definition_tokens_are_counted_separately(self) -> None:
        summaries.clear_summary_caches()

        file = _make_file()
        definition = _make_definition()

        file_client = _FakeClient(_FakeChatResponse("<gist>g</gist>full", 100, 20))
        with patch.object(summaries, "get_openai_client", return_value=file_client):
            await summaries.generate_file_summary_with_llm(file)

        def_client = _FakeClient(_FakeChatResponse("<gist>g</gist>full", 40, 8))
        with patch.object(summaries, "get_openai_client", return_value=def_client):
            await summaries.generate_definition_summary_with_llm(definition)

        summary = summaries.get_token_summary()

        assert summary["total_file_input_tokens"] == 100
        assert summary["total_file_output_tokens"] == 20
        assert summary["total_function_input_tokens"] == 40
        assert summary["total_function_output_tokens"] == 8
        assert summary["file_summaries_generated"] == 1
        assert summary["definition_summaries_generated"] == 1


# --------------------------------------------------------------------------- #
# Bug 20: retry decorators must only retry transient API errors.
# --------------------------------------------------------------------------- #


def _retry_predicate_decides_retry(func: Any, exc: BaseException) -> bool:
    """Ask a tenacity-decorated function's retry predicate about an exception.

    Inspects the configured ``retry`` predicate directly so the test is fast
    and does not depend on backoff timing or executing five real attempts.
    """
    retry_obj = func.retry
    outcome: Any = SimpleNamespace(failed=True, exception=lambda: exc)
    state = RetryCallState(retry_object=retry_obj, fn=func, args=(), kwargs={})
    state.outcome = outcome
    return bool(retry_obj.retry(state))


class TestRetryNarrowing:
    """Non-transient errors must surface immediately; transient ones retry."""

    def test_value_error_is_not_retried(self) -> None:
        for func in (
            summaries.generate_file_summary_with_llm,
            summaries.generate_definition_summary_with_llm,
        ):
            assert not _retry_predicate_decides_retry(func, ValueError("boom"))

    def test_transient_api_errors_are_retried(self) -> None:
        rate_limit = RateLimitError(
            "rate limited",
            response=SimpleNamespace(
                request=None, status_code=429, headers={}
            ),
            body=None,
        )
        timeout = APITimeoutError(request=None)
        connection = APIConnectionError(request=None)

        for func in (
            summaries.generate_file_summary_with_llm,
            summaries.generate_definition_summary_with_llm,
        ):
            for exc in (rate_limit, timeout, connection):
                assert _retry_predicate_decides_retry(func, exc)
