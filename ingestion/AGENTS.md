Agent Guidelines

Coding rules (enforced for new/changed code):
- Type hints: use Python 3.9+ syntax
  - Prefer `str | None`, `dict[str, T]`, `list[T]` over `Optional`, `Dict`, `List`.
- Unused results: assign to `_`
  - Example: `_ = some_async_call()` or `_ = session.flush()` when the value is not used.
- Time handling: use timezone‑aware UTC
  - Prefer `datetime.now(timezone.utc)` instead of `datetime.utcnow()`.

General project notes:
- Follow repository structure and naming conventions (snake_case modules, PascalCase classes).
- Keep changes minimal, focused, and well‑typed.
- Mask secrets in logs and responses.
