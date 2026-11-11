#!/usr/bin/env bash
# Phase 3 offline check: agent loop + scorer + tool-schema + tracing structure,
# driven by mock models against the real MCP tool/containers. No network.
set -u
cd "$(dirname "$0")/.."

VENV=harness/.venv
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV" || { echo "FAIL  could not create venv"; exit 1; }
fi
"$VENV/bin/pip" install -q -r harness/requirements.txt || { echo "FAIL  pip install"; exit 1; }

SECRET_API_KEY=bootstrap docker compose up -d --build >/dev/null 2>&1 \
  || { echo "FAIL  docker compose up"; exit 1; }
trap 'SECRET_API_KEY=unused docker compose down -v --remove-orphans >/dev/null 2>&1' EXIT

"$VENV/bin/python" -m harness.check_phase3
exit $?
