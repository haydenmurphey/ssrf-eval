"""The agent loop: system prompt + one MCP tool + 20-step cap + final answer.

The loop is agnostic to the model backend: it takes an `llm` callable with the
signature `(model_spec, messages, tools) -> (message, usage_dict)`, which is
`harness.llm.complete` for real runs and a scripted stand-in for the offline
check. The loop never sees the run's secret.
"""
import json
import time
from dataclasses import dataclass, field

from .briefs import BRIEFS, SYSTEM_PROMPT
from .config import STEP_CAP


@dataclass
class RunResult:
    final_answer: str
    steps: int
    tokens: int
    wall_time: float
    tool_responses: list = field(default_factory=list)
    trace_id: str | None = None
    stop_reason: str = "step_cap"  # answered | step_cap | error


def _normalize(message):
    """Return (content, tool_calls_as_dicts, assistant_message_dict).

    Accepts either a LiteLLM message object or a plain dict (from the mock).
    """
    if isinstance(message, dict):
        content = message.get("content")
        raw_tcs = message.get("tool_calls") or []
    else:
        content = message.content
        raw_tcs = message.tool_calls or []

    tcs = []
    for tc in raw_tcs:
        if isinstance(tc, dict):
            tid, fn = tc["id"], tc["function"]["name"]
            args = tc["function"]["arguments"]
        else:
            tid, fn, args = tc.id, tc.function.name, tc.function.arguments
        tcs.append({"id": tid, "type": "function",
                    "function": {"name": fn, "arguments": args}})

    asst = {"role": "assistant", "content": content}
    if tcs:
        asst["tool_calls"] = tcs
    return content, tcs, asst


async def run_agent(llm, tool, *, variant, model_id, run_id, tracer, model_spec) -> RunResult:
    tools = await tool.list_openai_tools()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": BRIEFS[variant]},
    ]
    tool_responses: list = []
    total_tokens = 0
    steps = 0
    final_answer = ""
    stop_reason = "step_cap"
    start = time.monotonic()

    with tracer.run(model_id=model_id, variant=variant, run_id=run_id):
        for steps in range(1, STEP_CAP + 1):
            with tracer.generation(name=f"step-{steps}",
                                   model=model_spec.get("model"),
                                   input=messages) as gen:
                message, usage, finish_reason = llm(model_spec, messages, tools)
                content, tcs, asst = _normalize(message)
                gen.update(
                    output=content if content else {"tool_calls": [t["function"]["name"] for t in tcs]},
                    usage_details={"input": usage["prompt_tokens"],
                                   "output": usage["completion_tokens"],
                                   "total": usage["total_tokens"]},
                )
            total_tokens += usage["total_tokens"]
            messages.append(asst)

            if not tcs:
                final_answer = content or ""
                # A safety-filter block returns empty content with this reason;
                # record it as a refusal rather than a normal empty answer.
                stop_reason = "refused" if finish_reason == "content_filter" else "answered"
                break

            for tc in tcs:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                with tracer.tool(name=name, input=args) as tspan:
                    result = await tool.call_tool_raw(name, args)
                    tspan.update(output=result)
                tool_responses.append(result)
                messages.append({"role": "tool", "tool_call_id": tc["id"],
                                 "name": name, "content": result})

        wall = time.monotonic() - start
        trace_id = tracer.trace_id

    # Flush only after the run span has ended, so the whole trace is exported.
    tracer.flush()

    return RunResult(final_answer=final_answer, steps=steps, tokens=total_tokens,
                     wall_time=wall, tool_responses=tool_responses,
                     trace_id=trace_id, stop_reason=stop_reason)
