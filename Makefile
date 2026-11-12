.PHONY: up down venv check-phase1 check-phase2 check-phase3 eval-one eval eval-summary label

# The per-run secret exists only in this recipe's environment; it is never written to disk.
up:
	SECRET_API_KEY="$$(openssl rand -hex 16)" docker compose up -d --build --force-recreate

down:
	SECRET_API_KEY=unused docker compose down -v --remove-orphans

venv:
	python3 -m venv harness/.venv
	harness/.venv/bin/pip install -q -r harness/requirements.txt

check-phase1:
	./scripts/check_phase1.sh

check-phase2:
	./scripts/check_phase2.sh

# Offline: mock models + real MCP tool/containers. No model API or Langfuse needed.
check-phase3:
	./scripts/check_phase3.sh

# Live single run (needs a populated .env): make eval-one MODEL=gemini-3.8-flash VARIANT=black-box
eval-one:
	MODEL="$(MODEL)" VARIANT="$(VARIANT)" ./scripts/eval_one.sh

# Benchmark batch (resumable). Override MODELS/VARIANTS/RUNS/OUT, e.g. make eval RUNS=1
eval:
	MODELS="$(MODELS)" VARIANTS="$(VARIANTS)" RUNS="$(RUNS)" OUT="$(OUT)" ./scripts/eval.sh

eval-summary:
	harness/.venv/bin/python -m harness.eval --summary-only --out "$(or $(OUT),results/runs.csv)"

# Apply the failure rubric to every run (needs results/trajectories.jsonl).
label:
	harness/.venv/bin/python -m harness.label
