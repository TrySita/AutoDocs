#!/usr/bin/env bash
set -euo pipefail

# Dev orchestrator: starts FastAPI (Uvicorn --reload) and Turbo dev (webview)
# - Requires: uv (Python), pnpm (Node)
# - Gracefully stops both on Ctrl+C

usage() {
  cat <<'USAGE'
Run development stack: Database, API, and Webview dev servers.

Usage:
  tools/dev.sh [options]

Options:
  --api-port N          API port (default: 8000)
  --web-port N          Web port env (default: 3000)
  --skip-api            Do not run the API dev server
  --skip-web            Do not run the web dev server
  --skip-db             Do not run the database
  --turbo-filter NAME   Pass a Turbo filter (e.g. @webapp)
  --sync                Ensure deps first (uv sync, pnpm i)
  -h, --help            Show this help

Notes:
  - DB uses:   docker compose up db
  - API uses:  cd ingestion && uv run uvicorn api.main:app --app-dir src --reload
  - Web uses:  cd webview   && pnpm dev  (i.e., Turbo dev)
USAGE
}

main() {
  local API_PORT=8000 WEB_PORT=3000 DO_API=1 DO_WEB=1 DO_DB=1 DO_SYNC=0 TURBO_FILTER=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --api-port) API_PORT=${2:-8000}; shift 2 ;;
      --web-port) WEB_PORT=${2:-3000}; shift 2 ;;
      --skip-api) DO_API=0; shift ;;
      --skip-web) DO_WEB=0; shift ;;
      --skip-db) DO_DB=0; shift ;;
      --turbo-filter) TURBO_FILTER=${2:-""}; shift 2 ;;
      --sync) DO_SYNC=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
  done

  local repo_root
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  if [[ $DO_SYNC -eq 1 ]]; then
    # Ensure Python deps
    if ! command -v uv >/dev/null 2>&1; then
      echo "[check] uv not found. Install from https://docs.astral.sh/uv/ or run without --sync" >&2
      exit 1
    fi
    echo "[sync] uv sync (ingestion)"
    (cd "$repo_root/ingestion" && uv sync)

    # Ensure Node deps
    if ! command -v pnpm >/dev/null 2>&1; then
      echo "[check] pnpm not found. Install pnpm or run without --sync" >&2
      exit 1
    fi
    echo "[sync] pnpm install (webview)"
    (cd "$repo_root/webview" && pnpm i)
  fi

  # Quick prereq check when running respective sides
  if [[ $DO_API -eq 1 ]]; then
    command -v uv >/dev/null 2>&1 || { echo "[check] uv is required for API dev" >&2; exit 1; }
  fi
  if [[ $DO_WEB -eq 1 ]]; then
    command -v pnpm >/dev/null 2>&1 || { echo "[check] pnpm is required for web dev" >&2; exit 1; }
  fi
  if [[ $DO_DB -eq 1 ]]; then
    command -v docker >/dev/null 2>&1 || { echo "[check] docker is required for database" >&2; exit 1; }
  fi

  # Symlink root .env to webapp folder if it exists and symlink doesn't exist
  if [[ -f "$repo_root/.env.local" && ! -L "$repo_root/webview/apps/webapp/.env.local" ]]; then
    echo "[env] Creating symlink: webapp/.env.local -> ../../../.env.local"
    ln -sf "../../../.env.local" "$repo_root/webview/apps/webapp/.env.local"
  fi

  # do the same for ingestion .env
  if [[ -f "$repo_root/.env.local" && ! -L "$repo_root/ingestion/.env.local" ]]; then
    echo "[env] Creating symlink: ingestion/.env.local -> ../.env.local"
    ln -sf "../.env.local" "$repo_root/ingestion/.env.local"
  fi

  echo "[dev] Starting dev servers (Ctrl+C to stop)"

  # Store PIDs to kill properly on exit
  local PIDS=()
  
  # Kill children on exit/INT/TERM
  cleanup() {
    echo
    echo "[dev] Stopping..."
    for pid in "${PIDS[@]}"; do
      kill -TERM "$pid" 2>/dev/null || true
    done
    # Give processes time to clean up
    sleep 1
    for pid in "${PIDS[@]}"; do
      kill -KILL "$pid" 2>/dev/null || true
    done
  }
  trap cleanup INT TERM EXIT

  # Database (Docker Compose)
  if [[ $DO_DB -eq 1 ]]; then
    (
      cd "$repo_root"
      echo "[db] docker compose up db"
      docker compose up db
    ) &
    PIDS+=($!)
  else
    echo "[db] skipped (--skip-db)"
  fi

  # API (Uvicorn with reload). Ensure imports resolve via --app-dir src.
  if [[ $DO_API -eq 1 ]]; then
    (
      cd "$repo_root/ingestion"
      echo "[api] uvicorn api.main:app on :$API_PORT"
      # EMBEDDINGS_API_KEY is respected if provided in environment
      uv run uvicorn api.main:app \
        --app-dir src \
        --reload \
        --host 0.0.0.0 \
        --port "$API_PORT"
    ) &
    PIDS+=($!)
  else
    echo "[api] skipped (--skip-api)"
  fi

  # Web (Turbo dev). Optionally pass a filter (e.g., @webapp)
  if [[ $DO_WEB -eq 1 ]]; then
    (
      cd "$repo_root/webview"
      echo "[web] turbo dev on :$WEB_PORT${TURBO_FILTER:+ (filter=$TURBO_FILTER)}"
      PORT="$WEB_PORT" pnpm dev ${TURBO_FILTER:+--filter "$TURBO_FILTER"}
    ) &
    PIDS+=($!)
  else
    echo "[web] skipped (--skip-web)"
  fi

  # Wait for any to exit; others are terminated by trap
  wait || true
}

main "$@"

