#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Build everything: Python (uv), TypeScript (pnpm+Turbo).

Usage:
  tools/build_all.sh [options]

Options:
  --skip-uv             Skip Python uv sync/export
  --skip-ts             Skip TypeScript install/build
  --no-export-reqs      Do not export uv requirements_lock.txt
  -h, --help            Show this help

USAGE
}

main() {
  local DO_UV=1 DO_TS=1 EXPORT_REQS=1

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --skip-uv) DO_UV=0; shift ;;
      --skip-ts) DO_TS=0; shift ;;
      --no-export-reqs) EXPORT_REQS=0; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
  done

  local repo_root
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  # --- Python (uv) ---
  if [[ $DO_UV -eq 1 ]]; then
    if ! command -v uv >/dev/null 2>&1; then
      echo "[python] uv not found. Install from https://docs.astral.sh/uv/ or run with --skip-uv" >&2
      exit 1
    fi
    echo "[python] uv sync..."
    (cd "$repo_root/ingestion" && uv sync)
    if [[ $EXPORT_REQS -eq 1 ]]; then
      echo "[python] exporting requirements_lock.txt..."
      (cd "$repo_root/ingestion" && uv export --frozen --format requirements-txt > requirements_lock.txt)
    else
      echo "[python] skipping export of requirements_lock.txt"
    fi
  else
    echo "[python] skipped (--skip-uv)"
  fi

  # --- TypeScript (pnpm + Turbo) ---
  if [[ $DO_TS -eq 1 ]]; then
    if ! command -v pnpm >/dev/null 2>&1; then
      echo "[ts] pnpm not found. Install pnpm or run with --skip-ts" >&2
      exit 1
    fi
    echo "[ts] pnpm install..."
    (cd "$repo_root/webview" && pnpm i)
    echo "[ts] pnpm build (Turbo)..."
    (cd "$repo_root/webview" && pnpm build)
  else
    echo "[ts] skipped (--skip-ts)"
  fi

  echo "\nAll done."
}

main "$@"

