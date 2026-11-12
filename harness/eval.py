"""Batch orchestrator: run the model x variant matrix and export results to CSV.

Reuses runner.eval_one for each run (fresh secret, dashboard recreate, traced
agent run, score). Appends each result to the CSV immediately, so an interrupted
batch loses nothing and can be resumed: on start we count existing rows per
(model, variant) and run only the remainder up to --runs ("top-up").

A run that raises is recorded as a row with stop_reason=error and the message,
so every row has a terminal status and no crash is left unexplained.
"""
import argparse
import asyncio
import csv
import os
from collections import Counter
from datetime import datetime, timezone

from . import config
from .runner import eval_one

FIELDS = ["timestamp", "model", "variant", "run_index", "run_id", "secret_sha",
          "success", "secret_in_tool_response", "steps", "tokens", "wall_time",
          "stop_reason", "trace_id", "error"]


def _read_rows(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _completed_counts(rows: list[dict]) -> Counter:
    # Count only non-error rows toward the target, so failed-to-run cells retry.
    return Counter((r["model"], r["variant"]) for r in rows if r.get("stop_reason") != "error")


def _append(path: str, row: dict):
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerow(row)
        f.flush()


async def run_batch(models, variants, runs, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    done = _completed_counts(_read_rows(out))

    planned = []
    for model in models:
        for variant in variants:
            have = done[(model, variant)]
            for i in range(have, runs):
                planned.append((model, variant, i))

    total = len(planned)
    print(f"Target {runs}/cell; {total} run(s) to do "
          f"({len(models)} models x {len(variants)} variants).")

    for n, (model, variant, idx) in enumerate(planned, 1):
        print(f"[{n}/{total}] {model} / {variant} #{idx} ... ", end="", flush=True)
        base = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "model": model, "variant": variant, "run_index": idx,
                "run_id": "", "secret_sha": "", "success": "",
                "secret_in_tool_response": "", "steps": "", "tokens": "",
                "wall_time": "", "stop_reason": "", "trace_id": "", "error": ""}
        try:
            rec = await eval_one(model, variant)
            base.update({k: rec.get(k, "") for k in FIELDS if k in rec})
            print(f"{rec['stop_reason']} success={rec['success']} "
                  f"steps={rec['steps']} tokens={rec['tokens']}")
        except Exception as e:  # noqa: BLE001 - record and keep going
            base["stop_reason"] = "error"
            base["error"] = f"{type(e).__name__}: {e}"[:300]
            print(f"ERROR {base['error']}")
        _append(out, base)

    _summary(out)


def _summary(out: str):
    rows = _read_rows(out)
    print(f"\n=== summary ({out}, {len(rows)} rows) ===")
    cells = sorted({(r["model"], r["variant"]) for r in rows})
    errors = sum(1 for r in rows if r["stop_reason"] == "error")
    for model, variant in cells:
        cell = [r for r in rows if r["model"] == model and r["variant"] == variant]
        succ = sum(1 for r in cell if r["success"] == "True")
        reasons = Counter(r["stop_reason"] for r in cell)
        print(f"  {model:16} {variant:9} n={len(cell):2} success={succ:2}  "
              f"{dict(reasons)}")
    print(f"  error rows: {errors}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen2.5:7b", "llama3.2:3b"])
    ap.add_argument("--variants", nargs="+", default=list(config.VARIANTS))
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--out", default="results/runs.csv")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()

    for m in args.models:
        config.model_spec(m)  # validate ids up front
    for v in args.variants:
        if v not in config.VARIANTS:
            raise SystemExit(f"unknown variant '{v}'")

    if args.summary_only:
        _summary(args.out)
        return
    asyncio.run(run_batch(args.models, args.variants, args.runs, args.out))


if __name__ == "__main__":
    main()
