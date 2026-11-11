"""Run one model x variant against a fresh secret and score it.

The secret is generated here, injected into the dashboard, and handed only to
the scorer. The agent never receives it. Records carry a sha prefix of the
secret for correlation, never the value.
"""
import argparse
import asyncio
import hashlib
import secrets

from . import config, env
from .agent import run_agent
from .llm import complete
from .mcp_client import http_tool
from .scorer import score
from .tracing import get_tracer


async def eval_one(model_id: str, variant: str, *, llm=complete) -> dict:
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
    return {
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
