#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/python"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. See https://docs.astral.sh/uv/ for install instructions." >&2
  exit 1
fi

echo "Exporting frozen requirements for Bazel -> python/requirements_lock.txt"
uv export --frozen --format requirements-txt > requirements_lock.txt
echo "Done."

