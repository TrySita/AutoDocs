"""Bug 31: deprecated naive ``datetime.utcnow()`` usage.

These tests pin the behavioral edge that timestamps must be timezone-aware
(UTC). A naive ``datetime.utcnow()`` produces a timestamp with no offset,
which is both deprecated in Python 3.12+ and ambiguous when serialized.
"""

from datetime import datetime

from ast_parsing.types import ParsedASTResult


def test_parsed_ast_result_generated_on_is_timezone_aware():
    """The ``generatedOn`` metadata timestamp must carry a UTC offset.

    ``datetime.utcnow().isoformat()`` yields a naive ISO string with no
    offset (e.g. ``2026-06-05T12:00:00``); parsing it back leaves
    ``tzinfo`` as ``None``. A timezone-aware UTC timestamp serializes with
    ``+00:00`` and round-trips to an aware datetime.
    """
    result = ParsedASTResult(
        directory_path="/tmp/repo",
        total_files=1,
        parsed_files=1,
        unparsed_files=0,
    )

    generated_on = result.metadata["generatedOn"]
    parsed = datetime.fromisoformat(generated_on)

    assert parsed.tzinfo is not None, (
        f"generatedOn must be timezone-aware, got naive value {generated_on!r}"
    )
    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0
