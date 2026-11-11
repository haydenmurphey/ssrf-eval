#!/usr/bin/env bash
# Live single run. Needs a populated .env (Langfuse keys, OLLAMA_BASE, GEMINI_API_KEY).
#   make eval-one MODEL=gemini-2.0-flash VARIANT=black-box
set -u
cd "$(dirname "$0")/.."

: "${MODEL:?set MODEL, e.g. gemini-2.0-flash or qwen2.5:7b}"
: "${VARIANT:?set VARIANT, e.g. black-box or hinted}"

VENV=harness/.venv
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV" || { echo "FAIL  could not create venv"; exit 1; }
fi
"$VENV/bin/pip" install -q -r harness/requirements.txt || { echo "FAIL  pip install"; exit 1; }

# Bring the stack up if it is not already running (bootstrap secret; the runner
# injects a fresh per-run secret into the dashboard).
if [ -z "$(docker compose ps -q mcp-server 2>/dev/null)" ]; then
  SECRET_API_KEY=bootstrap docker compose up -d --build >/dev/null 2>&1 \
    || { echo "FAIL  docker compose up"; exit 1; }
fi

"$VENV/bin/python" -m harness.runner --model "$MODEL" --variant "$VARIANT"
