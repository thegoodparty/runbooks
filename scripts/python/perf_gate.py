#!/usr/bin/env python3
"""Performance gate: the objective head of the two-headed eval.

Judges HOW a run executed (did it produce an artifact, at what cost/turns/errors), not
whether the output is good (that's the quality rubric). One hard, defensible failure:
a run that produced no valid artifact. Cost/turns/tool-error ceilings are FLAGs for review,
not hard fails, because a legitimately complex run may cost more without being wrong.

For relative A/B gating (did v2 regress vs v1 on the same inputs), use
`eval_trajectory.py --ab`; this module is the absolute per-run / per-batch health gate.

Thresholds are PROVISIONAL, set near p90 of a 30-run meeting_briefing sample
(cost median 3.89 / p90 5.92 / max 10.92; turns median 52 / p90 75 / max 126). They are
meant to flag the worst ~10% for review, and should be re-derived per experiment on a
larger sample before being treated as firm.

Usage:
  uv run python perf_gate.py <trace_dir> --bucket gp-agent-artifacts-prod --exp meeting_briefing
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

from eval_trajectory import score, _load

DEFAULT_THRESHOLDS = {"cost_max": 6.0, "turns_max": 80, "tool_errors_max": 2}
# Statuses that mean the run did not deliver a usable artifact -> hard FAIL.
FAIL_STATUSES = {"NO_ARTIFACT", "BAD_JSON", "error"}


def evaluate(metrics: dict, status: str, thresholds: dict | None = None) -> dict:
    """Pure gate decision for one run. Returns {verdict: PASS|FLAG|FAIL, reasons:[...]}."""
    t = thresholds or DEFAULT_THRESHOLDS
    if status in FAIL_STATUSES:
        return {"verdict": "FAIL", "reasons": [f"no valid artifact (status={status})"]}

    reasons = []
    cost = metrics.get("cost") or 0.0
    turns = metrics.get("turns")
    errs = metrics.get("tool_errors") or 0
    if cost > t["cost_max"]:
        reasons.append(f"cost ${cost:.2f} > ${t['cost_max']:.2f}")
    if turns is None:
        reasons.append("no result record (incomplete trace)")
    elif turns > t["turns_max"]:
        reasons.append(f"turns {turns} > {t['turns_max']}")
    if errs > t["tool_errors_max"]:
        reasons.append(f"tool_errors {errs} > {t['tool_errors_max']}")
    return {"verdict": "FLAG" if reasons else "PASS", "reasons": reasons}


def _artifact_status(rid: str, bucket: str, exp: str) -> str:
    env = {**os.environ}
    p = subprocess.run(
        ["aws", "s3", "cp", f"s3://{bucket}/{exp}/{rid}/artifact.json", "-"],
        capture_output=True, text=True, env=env,
    )
    if p.returncode != 0 or not p.stdout.strip():
        return "NO_ARTIFACT"
    try:
        return json.loads(p.stdout).get("briefing_status") or "NULL_STATUS"
    except json.JSONDecodeError:
        return "BAD_JSON"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace_dir")
    ap.add_argument("--bucket", default="gp-agent-artifacts-prod")
    ap.add_argument("--exp", required=True)
    ap.add_argument("--cost-max", type=float)
    ap.add_argument("--turns-max", type=int)
    ap.add_argument("--tool-errors-max", type=int)
    a = ap.parse_args()
    th = dict(DEFAULT_THRESHOLDS)
    if a.cost_max is not None:
        th["cost_max"] = a.cost_max
    if a.turns_max is not None:
        th["turns_max"] = a.turns_max
    if a.tool_errors_max is not None:
        th["tool_errors_max"] = a.tool_errors_max

    counts = {"PASS": 0, "FLAG": 0, "FAIL": 0}
    no_artifact = 0
    print(f"{'run':14s}{'status':17s}{'verdict':8s}{'cost':>7s}{'turns':>6s}{'errs':>5s}  reasons")
    print("-" * 78)
    for f in sorted(glob.glob(os.path.join(a.trace_dir, "*.jsonl"))):
        if not os.path.getsize(f):
            continue
        rid = os.path.basename(f)[:-6]
        m = score(_load(f), [], None)
        status = _artifact_status(rid, a.bucket, a.exp)
        r = evaluate(m, status, th)
        counts[r["verdict"]] += 1
        no_artifact += status == "NO_ARTIFACT"
        print(f"{rid[:13]:14s}{status[:16]:17s}{r['verdict']:8s}{(m.get('cost') or 0):>7.2f}"
              f"{str(m.get('turns')):>6s}{m.get('tool_errors', 0):>5d}  {'; '.join(r['reasons'])}")
    n = sum(counts.values())
    print("-" * 78)
    print(f"runs: {n}  PASS={counts['PASS']}  FLAG={counts['FLAG']}  FAIL={counts['FAIL']}")
    if n:
        print(f"no-artifact failure rate: {no_artifact}/{n} = {100*no_artifact/n:.0f}%")
    print(f"thresholds: {th}  (provisional; re-derive per experiment on a larger sample)")


if __name__ == "__main__":
    main()
