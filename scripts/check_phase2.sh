#!/usr/bin/env bash
# Phase 2 check: builds the stack (incl. mcp-server), sets up the harness venv,
# and runs the in-process oracle/do-nothing/allowlist checks. The per-run secret
# is generated inside the Python process and never touches disk.
set -u
cd "$(dirname "$0")/.."

VENV=harness/.venv
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV" || { echo "FAIL  could not create venv"; exit 1; }
fi
"$VENV/bin/pip" install -q -r harness/requirements.txt || { echo "FAIL  pip install"; exit 1; }

# Bootstrap secret just satisfies the compose `:?` guard at startup; the oracle
# loop overwrites it with a fresh per-run secret on the dashboard.
SECRET_API_KEY=bootstrap docker compose up -d --build >/dev/null 2>&1 \
  || { echo "FAIL  docker compose up"; exit 1; }
trap 'SECRET_API_KEY=unused docker compose down -v --remove-orphans >/dev/null 2>&1' EXIT

"$VENV/bin/python" -m harness.check_phase2
exit $?
