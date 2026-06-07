#!/usr/bin/env python3
"""Real-time performance monitor: gate the latest deployed runs against an experiment's
adopted perf config and ALARM when execution health drifts above its baseline.

Pairs with derive_perf_thresholds.py (which produces the config + baseline) and perf_gate.py
(which scores one batch). Run it on a cadence (a /loop, cron, or launchd job) pointed at dev.

Usage:
  AWS_PROFILE=work AWS_REGION=us-west-2 uv run python perf_monitor.py \
    --config experiment-evals/<exp>/perf.json --env dev -n 30
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile

from eval_trajectory import score, _load
from perf_gate import evaluate, artifact_status, NO_ARTIFACT

TOL_NO_ARTIFACT = 0.10  # alarm if the live no-artifact rate exceeds baseline by more than this
TOL_FLAG = 0.20         # alarm if the live FLAG rate exceeds this


def drift_alarm(live_no_artifact_rate, live_flag_rate, baseline_no_artifact_rate,
                tol_no_artifact=TOL_NO_ARTIFACT, tol_flag=TOL_FLAG) -> dict:
    """Pure drift decision. Alarm if no-artifact rate drifts above baseline+tol, or FLAG rate spikes."""
    base = baseline_no_artifact_rate or 0.0
    reasons = []
    if live_no_artifact_rate > base + tol_no_artifact:
        reasons.append(f"no-artifact rate {live_no_artifact_rate:.0%} > baseline {base:.0%} + {tol_no_artifact:.0%}")
    if live_flag_rate > tol_flag:
        reasons.append(f"FLAG rate {live_flag_rate:.0%} > {tol_flag:.0%}")
    return {"alarm": bool(reasons), "reasons": reasons}


def _latest_run_ids(bucket, exp, n):
    p = subprocess.run(["aws", "s3", "ls", f"s3://{bucket}/{exp}/"],
                       capture_output=True, text=True, env={**os.environ})
    ids = [ln.split("PRE ")[-1].strip().rstrip("/") for ln in p.stdout.splitlines() if "PRE " in ln]
    ids = [i for i in ids if len(i) >= 8 and all(c in "0123456789abcdef" for c in i[:8])]
    return sorted(ids)[-n:]  # UUIDv7 is time-ordered: the tail is the newest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--env", default="dev")
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("--bucket")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    exp = cfg["experiment"]
    bucket = a.bucket or f"gp-agent-artifacts-{a.env}"
    status_field = cfg.get("status_field")

    runs = _latest_run_ids(bucket, exp, a.n)
    counts = {"PASS": 0, "FLAG": 0, "FAIL": 0}
    no_artifact = 0
    with tempfile.TemporaryDirectory() as td:
        for rid in runs:
            tf = f"{td}/{rid}.jsonl"
            subprocess.run(["aws", "s3", "cp",
                            f"s3://{bucket}/{exp}/{rid}/logs/workspace/conversation.jsonl", tf, "--quiet"],
                           env={**os.environ})
            if not (os.path.exists(tf) and os.path.getsize(tf)):
                continue
            m = score(_load(tf), [], None)
            status = artifact_status(rid, bucket, exp, status_field)
            r = evaluate(m, status, cfg)
            counts[r["verdict"]] += 1
            no_artifact += status == NO_ARTIFACT

    n = sum(counts.values())
    na_rate = no_artifact / n if n else 0.0
    flag_rate = counts["FLAG"] / n if n else 0.0
    alarm = drift_alarm(na_rate, flag_rate, cfg.get("no_artifact_rate"))

    print(f"[perf-monitor] {exp} @ {a.env}  latest {n} runs")
    print(f"  PASS={counts['PASS']} FLAG={counts['FLAG']} FAIL={counts['FAIL']}")
    print(f"  no-artifact rate: {na_rate:.0%} (baseline {(cfg.get('no_artifact_rate') or 0):.0%})   FLAG rate: {flag_rate:.0%}")
    if alarm["alarm"]:
        print(f"  ALARM: {'; '.join(alarm['reasons'])}")
    else:
        print("  OK (within baseline tolerance)")
    return 1 if alarm["alarm"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
