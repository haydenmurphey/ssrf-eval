"""Run one model x variant against a fresh secret and score it.

The secret is generated here, injected into the dashboard, and handed only to
the scorer. The agent never receives it. Records carry a sha prefix of the
secret for correlation, never the value.
"""
import argparse
import asyncio
import hashlib
import json
import os
import secrets

from . import config, env
from .agent import run_agent
from .llm import complete
from .mcp_client import http_tool
from .scorer import score
from .tracing import get_tracer

TRAJECTORIES = "results/trajectories.jsonl"


def _redact(text, secret: str) -> str:
    """Never let the per-run secret reach disk — replace it with a placeholder."""
    return (text or "").replace(secret, "<SECRET>")


def _write_trajectory(record: dict, result, secret: str):
    """Append a per-run trajectory for offline rubric labeling (secret redacted)."""
    os.makedirs(os.path.dirname(TRAJECTORIES) or ".", exist_ok=True)
    row = {
        "run_id": record["run_id"],
        "model": record["model"],
        "variant": record["variant"],
        "stop_reason": record["stop_reason"],
        "n_tool_calls": len(result.tool_calls),
        "tool_calls": result.tool_calls,  # names + arguments (URLs/body) — no secret
        "final_answer": _redact(result.final_answer, secret),
    }
    with open(TRAJECTORIES, "a") as f:
        f.write(json.dumps(row) + "\n")


async def eval_one(model_id: str, variant: str, *, llm=complete, log_trajectory=True) -> dict:
    spec = config.model_spec(model_id)
    if variant not in config.VARIANTS:
        raise SystemExit(f"unknown variant '{variant}'; known: {', '.join(config.VARIANTS)}")

    secret = secrets.token_hex(16)
    run_id = secrets.token_hex(4)
    env.recreate_dashboard(secret)
    tracer = get_tracer()

    async with http_tool() as tool:
        await env.wait_ready(tool)
        result = await run_agent(llm, tool, variant=variant, model_id=model_id,
                                 run_id=run_id, tracer=tracer, model_spec=spec)

    success = score(result.final_answer, secret)
    secret_in_tool = any(secret in r for r in result.tool_responses)
    record = {
        "model": model_id,
        "variant": variant,
        "run_id": run_id,
        "secret_sha": hashlib.sha256(secret.encode()).hexdigest()[:12],
        "success": success,
        "secret_in_tool_response": secret_in_tool,
        "steps": result.steps,
        "tokens": result.tokens,
        "wall_time": round(result.wall_time, 2),
        "stop_reason": result.stop_reason,
        "trace_id": result.trace_id,
    }
    if log_trajectory:
        _write_trajectory(record, result, secret)
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(config.MODELS))
    ap.add_argument("--variant", required=True, choices=list(config.VARIANTS))
    args = ap.parse_args()

    record = asyncio.run(eval_one(args.model, args.variant))
    print()
    for k, v in record.items():
        print(f"  {k}: {v}")
    if record["trace_id"]:
        print(f"\n  Langfuse: {config.LANGFUSE_HOST}  (trace id {record['trace_id']})")
    else:
        print("\n  (Langfuse disabled — no LANGFUSE_* keys in .env)")


if __name__ == "__main__":
    main()
