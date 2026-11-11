"""Phase 3 offline check: prove the agent loop, scorer, tool-schema conversion
and tracing structure work end to end, using scripted mock models and the real
MCP tool/containers — no model API or Langfuse network access.

The live PRD check (one real local run + one real API run, both visible in
Langfuse) is run separately by the user with a populated .env.
"""
import asyncio
import secrets
import sys
from contextlib import contextmanager

from . import config, env
from .agent import run_agent
from .mcp_client import http_tool
from .mock_llm import do_nothing_mock, exploit_mock
from .scorer import score
from .tracing import LangfuseTracer, NullTracer, _NullSpan, get_tracer

fails = 0
MODEL_ID = "gemini-3.8-flash"  # label only; the mock ignores it (no network)


def _p(ok: bool, msg: str):
    global fails
    print(f"{'PASS' if ok else 'FAIL'}  {msg}")
    if not ok:
        fails += 1


class FakeTracer:
    enabled = True

    def __init__(self):
        self.runs = self.generations = self.tools = 0
        self.trace_id = "fake-trace"

    @contextmanager
    def run(self, **kwargs):
        self.runs += 1
        yield self

    @contextmanager
    def generation(self, **kwargs):
        self.generations += 1
        yield _NullSpan()

    @contextmanager
    def tool(self, **kwargs):
        self.tools += 1
        yield _NullSpan()

    def flush(self):
        pass


async def main() -> int:
    spec = config.model_spec(MODEL_ID)

    async with http_tool() as tool:
        print("--- A. MCP -> OpenAI tool schema")
        tools = await tool.list_openai_tools()
        names = [t["function"]["name"] for t in tools]
        _p(names == ["http_request"], f"exactly one http_request tool (got {names})")
        _p(isinstance(tools[0]["function"].get("parameters"), dict),
           "tool exposes a JSON-schema parameters object")

        for variant in config.VARIANTS:
            print(f"--- B. exploit agent, variant={variant}")
            secret = secrets.token_hex(16)
            env.recreate_dashboard(secret)
            await env.wait_ready(tool)
            tracer = FakeTracer()
            res = await run_agent(exploit_mock, tool, variant=variant,
                                  model_id=MODEL_ID, run_id="chk", tracer=tracer,
                                  model_spec=spec)
            _p(score(res.final_answer, secret), f"{variant}: final answer contains the secret")
            _p(res.stop_reason == "answered", f"{variant}: stopped by answering (got {res.stop_reason})")
            _p(0 < res.steps <= config.STEP_CAP, f"{variant}: step count in range (got {res.steps})")
            _p(res.tokens > 0, f"{variant}: tokens recorded (got {res.tokens})")
            _p(any(secret in r for r in res.tool_responses),
               f"{variant}: secret observed in a tool response")
            _p(tracer.runs == 1 and tracer.generations == res.steps and tracer.tools == 3,
               f"{variant}: tracer saw 1 run, {res.steps} generations, {tracer.tools} tool spans")

        print("--- C. do-nothing agent (NullTracer path)")
        # get_tracer() picks the tracer from whether .env has keys; both are valid.
        if config.langfuse_enabled():
            _p(isinstance(get_tracer(), LangfuseTracer), "LANGFUSE_* keys present -> LangfuseTracer")
        else:
            _p(isinstance(get_tracer(), NullTracer), "no LANGFUSE_* keys -> NullTracer")
        secret = secrets.token_hex(16)
        env.recreate_dashboard(secret)
        await env.wait_ready(tool)
        res = await run_agent(do_nothing_mock, tool, variant="black-box",
                              model_id=MODEL_ID, run_id="chk", tracer=NullTracer(),
                              model_spec=spec)
        _p(not score(res.final_answer, secret), "do-nothing: final answer lacks the secret")
        _p(res.steps == 1 and res.stop_reason == "answered",
           f"do-nothing: one step, answered (got {res.steps}, {res.stop_reason})")

    print()
    print("Phase 3 offline check: ALL PASS" if fails == 0 else f"Phase 3 offline check: {fails} FAILED")
    return fails


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
