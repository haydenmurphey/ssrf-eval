"""Langfuse v3 tracing with a no-op fallback.

If Langfuse keys are present (live runs), `get_tracer()` returns a real tracer
that opens a run-level trace and nests a `generation` per model call and a
`tool` span per MCP call, tagged with model/variant/run id. If keys are absent
(the offline check), a null tracer with the same interface is returned so the
agent loop runs unchanged with no network.
"""
from contextlib import contextmanager

from . import config


class _NullSpan:
    def update(self, **kwargs):
        pass


class NullTracer:
    enabled = False
    trace_id = None

    @contextmanager
    def run(self, *, model_id, variant, run_id):
        yield self

    @contextmanager
    def generation(self, *, name, model, input):
        yield _NullSpan()

    @contextmanager
    def tool(self, *, name, input):
        yield _NullSpan()

    def flush(self):
        pass


class LangfuseTracer:
    enabled = True

    def __init__(self, client):
        self._lf = client
        self.trace_id = None

    @contextmanager
    def run(self, *, model_id, variant, run_id):
        from langfuse import propagate_attributes

        with self._lf.start_as_current_observation(
            as_type="span", name=f"ssrf-eval:{variant}"
        ) as span:
            # propagate_attributes is the v4 way to set trace-level name/tags/metadata;
            # it also propagates them to the child generation/tool spans below.
            with propagate_attributes(
                trace_name=f"ssrf-eval:{model_id}:{variant}:{run_id}",
                tags=[f"model:{model_id}", f"variant:{variant}", f"run:{run_id}"],
                metadata={"model": model_id, "variant": variant, "run_id": run_id},
            ):
                self.trace_id = self._lf.get_current_trace_id()
                yield self
                span.update(output="run complete")

    @contextmanager
    def generation(self, *, name, model, input):
        with self._lf.start_as_current_observation(
            as_type="generation", name=name, model=model, input=input
        ) as gen:
            yield gen

    @contextmanager
    def tool(self, *, name, input):
        with self._lf.start_as_current_observation(
            as_type="tool", name=name, input=input
        ) as t:
            yield t

    def flush(self):
        self._lf.flush()


def get_tracer():
    if not config.langfuse_enabled():
        return NullTracer()
    from langfuse import get_client

    return LangfuseTracer(get_client())
