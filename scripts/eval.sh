#!/usr/bin/env bash
# Benchmark batch. Brings the stack up once, then runs the model x variant matrix,
# appending to a resumable CSV. Leaves the stack up (the batch can be resumed);
# run `make down` when finished.
#   make eval                 # defaults: both local models, 10/cell -> results/runs.csv
#   make eval RUNS=1          # smoke (1/cell)
#   MODELS="qwen2.5:7b llama3.2:3b gemini-3.8-flash" make eval   # add the API model
set -u
cd "$(dirname "$0")/.."

MODELS="${MODELS:-qwen2.5:7b llama3.2:3b}"
VARIANTS="${VARIANTS:-black-box hinted}"
RUNS="${RUNS:-10}"
OUT="${OUT:-results/runs.csv}"

VENV=harness/.venv
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV" || { echo "FAIL  could not create venv"; exit 1; }
fi
"$VENV/bin/pip" install -q -r harness/requirements.txt || { echo "FAIL  pip install"; exit 1; }

if [ -z "$(docker compose ps -q mcp-server 2>/dev/null)" ]; then
  SECRET_API_KEY=bootstrap docker compose up -d --build >/dev/null 2>&1 \
    || { echo "FAIL  docker compose up"; exit 1; }
fi

"$VENV/bin/python" -m harness.eval --models $MODELS --variants $VARIANTS --runs "$RUNS" --out "$OUT"
