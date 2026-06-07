#!/usr/bin/env python3
"""Derive a per-experiment performance config (the 'performance rubric') from real runs.

Performance is objective, so no agent or judge is needed — this is measurement. It samples
an experiment's deployed runs, DISCOVERS its status field (which varies: briefing_status /
status / none), computes the cost/turns/error distribution over artifact-producing runs, sets
FLAG ceilings at p95, infers fail-status values heuristically (a status named error/failed),
and emits a config consumable by perf_gate.py --config.

Usage: AWS_PROFILE=work AWS_REGION=us-west-2 uv run python derive_perf_thresholds.py <exp> --env dev -n 60
"""
import argparse
import json
import os
import random
import statistics as st
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from eval_trajectory import score, _load

FAIL_WORDS = ("error", "failed", "failure")


def _aws(*args):
    return subprocess.run(["aws", *args], capture_output=True, text=True, env={**os.environ})


def _list_runs(bucket, exp, n):
    p = _aws("s3", "ls", f"s3://{bucket}/{exp}/")
    ids = [ln.split("PRE ")[-1].strip().rstrip("/") for ln in p.stdout.splitlines() if "PRE " in ln]
    ids = [i for i in ids if len(i) >= 8 and all(c in "0123456789abcdef" for c in i[:8])]
    random.shuffle(ids)
    return ids[:n]


def pct(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = max(0, min(len(vals) - 1, int(round(p / 100 * (len(vals) - 1)))))
    return vals[k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp")
    ap.add_argument("--env", default="dev")
    ap.add_argument("-n", type=int, default=60)
    ap.add_argument("--bucket")
    a = ap.parse_args()
    bucket = a.bucket or f"gp-agent-artifacts-{a.env}"
    out = f"outputs/perf-eval/{a.exp}/derive-{a.env}"
    os.makedirs(f"{out}/traces", exist_ok=True)
    os.makedirs(f"{out}/artifacts", exist_ok=True)
    runs = _list_runs(bucket, a.exp, a.n * 2)  # oversample; some runs lack files

    def pull(rid):
        _aws("s3", "cp", f"s3://{bucket}/{a.exp}/{rid}/logs/workspace/conversation.jsonl", f"{out}/traces/{rid}.jsonl", "--quiet")
        _aws("s3", "cp", f"s3://{bucket}/{a.exp}/{rid}/artifact.json", f"{out}/artifacts/{rid}.json", "--quiet")

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(pull, runs))

    sfields = Counter()
    rows = []
    for rid in runs:
        tf, af = f"{out}/traces/{rid}.jsonl", f"{out}/artifacts/{rid}.json"
        if not (os.path.exists(tf) and os.path.getsize(tf)):
            continue
        m = score(_load(tf), [], None)
        art = None
        if os.path.exists(af) and os.path.getsize(af):
            try:
                art = json.load(open(af))
            except json.JSONDecodeError:
                art = "BAD"
        rows.append((rid, m, art))
        if isinstance(art, dict):
            for k in art:
                if "status" in k.lower():
                    sfields[k] += 1
    status_field = sfields.most_common(1)[0][0] if sfields else None

    statuses = Counter()
    present, noart = [], 0
    for _rid, m, art in rows:
        if art is None:
            noart += 1
            continue
        if art == "BAD":
            continue
        present.append(m)
        if status_field and isinstance(art, dict):
            statuses[str(art.get(status_field))] += 1
    fail_values = sorted({s for s in statuses if any(w in s.lower() for w in FAIL_WORDS)})
    # "error" is universally a failure status; include it for any status-field experiment even
    # if it didn't appear in the sample (failures are rare, so a 50-run sample often misses them).
    if status_field and "error" not in fail_values:
        fail_values.append("error")

    costs = [m["cost"] for m in present]
    turns = [m["turns"] for m in present if m["turns"] is not None]
    errs = [m["tool_errors"] for m in present]
    thresholds = {
        "cost_max": round(pct(costs, 95) or 0, 2),
        "turns_max": pct(turns, 95) or 0,
        "tool_errors_max": max(2, pct(errs, 90) or 0),
    }
    cfg = {
        "experiment": a.exp, "env": a.env, "n": len(rows),
        "status_field": status_field, "fail_values": fail_values,
        "thresholds": thresholds,
        "no_artifact_rate": round(noart / len(rows), 3) if rows else None,
        "status_counts": dict(statuses),
        "distribution": {
            "cost": {"median": round(st.median(costs), 2) if costs else None, "p95": thresholds["cost_max"], "max": round(max(costs), 2) if costs else None},
            "turns": {"median": st.median(turns) if turns else None, "p95": thresholds["turns_max"], "max": max(turns) if turns else None},
        },
    }
    cfgpath = f"outputs/perf-eval/{a.exp}/{a.exp}.perf.json"
    json.dump(cfg, open(cfgpath, "w"), indent=2)
    print(json.dumps(cfg, indent=2))
    print(f"\nwrote {cfgpath}")


if __name__ == "__main__":
    main()
