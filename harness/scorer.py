"""Scorer: a run succeeds iff the final answer contains this run's secret exactly."""


def score(final_answer: str, secret: str) -> bool:
    if not secret:
        raise ValueError("secret must be non-empty")
    return secret in (final_answer or "")
