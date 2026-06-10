#!/usr/bin/env python3
"""A/B savings table — per-input v1-vs-v2 cost/turns/planning, joined to TRUE artifact status.

Complements `eval_trajectory.py --ab`: that diffs two trace dirs using a status REGEX heuristic;
this pulls each run's artifact.json from S3 for the real `status_field` outcome, so the
outcome-parity check is exact. Pairs whose outcome diverges across arms are flagged and EXCLUDED
from the aggregate (a different outcome means the arms did different work — the $ delta is
confounded, per books/evaluate-experiment-runs.md).

Input is a runs-map TSV with a header and columns: exp, arm (ctrl|treat), path, label, run_id.
(The same map you build when dispatching the A/B — one row per dispatched run.)

Usage:
  uv run python ab_savings.py runs_map.tsv --bucket gp-agent-artifacts-dev --status-field briefing_status
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess

from eval_trajectory import score, parse_trace

NO_ARTIFACT = "NO_ARTIFACT"


def _s3_text(bucket: str, key: str) -> str | None:
    p = subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/{key}", "-"],
                       capture_output=True, text=True, env={**os.environ})
    return p.stdout if p.returncode == 0 and p.stdout.strip() else None


def fetch_artifact(bucket: str, exp: str, rid: str):
    """The run's artifact.json as a dict, or None if it never produced one / is unparseable."""
    txt = _s3_text(bucket, f"{exp}/{rid}/artifact.json")
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def render_verbatim(pairs) -> str:
    """Side-by-side full artifacts for a human quality read at the end of an A/B.

    pairs: list of (label, ctrl_artifact|None, treat_artifact|None). Renders each input's
    control then treatment artifact as untruncated pretty JSON, in the given order, so the
    apples-to-apples comparison reads left-to-right. A missing arm is shown, never dropped.
    """
    out = ["# A/B verbatim artifacts — control (v1) vs treatment (v2)",
           "", "_Full, untruncated output per input. Read for quality parity._", ""]
    for label, ctrl, treat in pairs:
        out.append(f"## {label}")
        out.append("")
        for arm, art in (("control (v1)", ctrl), ("treatment (v2)", treat)):
            out.append(f"### {arm}")
            if art is None:
                out.append("_(no artifact produced)_")
            else:
                out.append("```json")
                out.append(json.dumps(art, indent=2, ensure_ascii=False))
                out.append("```")
            out.append("")
    return "\n".join(out)


def run_metrics(bucket: str, exp: str, rid: str, status_field: str | None):
    """Pull one run's trace + artifact; return (status, {turns,cost,planning_pct,tool_errors}) or None."""
    trace = _s3_text(bucket, f"{exp}/{rid}/logs/workspace/conversation.jsonl")
    art_txt = _s3_text(bucket, f"{exp}/{rid}/artifact.json")
    if trace is None:
        return None
    m = score(trace, [], None)
    status = NO_ARTIFACT
    if art_txt:
        try:
            status = json.loads(art_txt).get(status_field) if status_field else "ok"
        except json.JSONDecodeError:
            status = "BAD_JSON"
    return status, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs_map", help="TSV: exp, arm(ctrl|treat), path, label, run_id (with header)")
    ap.add_argument("--bucket", default="gp-agent-artifacts-dev")
    ap.add_argument("--status-field", default="briefing_status",
                    help="artifact field holding the run outcome (empty string = none)")
    ap.add_argument("--verbatim", metavar="PATH",
                    help="also write a markdown of each input's FULL control-vs-treatment "
                         "artifact (untruncated) for a human quality read")
    a = ap.parse_args()
    status_field = a.status_field or None

    rows = list(csv.DictReader(open(a.runs_map), delimiter="\t"))
    by: dict[str, dict] = {}
    for r in rows:
        by.setdefault(r["label"], {})[r["arm"]] = r
    order = [r["label"] for r in rows if r["arm"] == "ctrl"] or list(by)

    hdr = (f'{"input":24s}{"v1$":>7s}{"v2$":>7s}{"$save":>7s}'
           f'{"v1t":>5s}{"v2t":>5s}{"tsave":>7s}{"v1pl%":>7s}{"v2pl%":>7s}  note')
    print(hdr)
    print("-" * len(hdr))
    cc = tc = ct = tt = npairs = 0
    for lbl in order:
        g = by.get(lbl, {})
        cm = run_metrics(a.bucket, g["ctrl"]["exp"], g["ctrl"]["run_id"], status_field) if "ctrl" in g else None
        tm = run_metrics(a.bucket, g["treat"]["exp"], g["treat"]["run_id"], status_field) if "treat" in g else None
        if not (cm and tm):
            miss = ",".join(x for x, v in (("v1", cm), ("v2", tm)) if not v)
            print(f'{lbl:24s}{"":>53s}  waiting ({miss})')
            continue
        cs, c = cm
        ts, t = tm
        parity = cs == ts
        note = "" if parity else f"MISMATCH v1={cs} v2={ts} (confounded, excluded)"
        ds = c["cost"] - t["cost"]
        dt = (c["turns"] or 0) - (t["turns"] or 0)
        print(f'{lbl:24s}{c["cost"]:>7.2f}{t["cost"]:>7.2f}{ds:>+7.2f}'
              f'{str(c["turns"]):>5s}{str(t["turns"]):>5s}{dt:>+7d}'
              f'{c["planning_pct"]:>7.1f}{t["planning_pct"]:>7.1f}  {note}')
        if parity:
            cc += c["cost"]; tc += t["cost"]; ct += c["turns"] or 0; tt += t["turns"] or 0; npairs += 1
    print("-" * len(hdr))
    if npairs:
        print(f'{f"CLEAN PAIRS ({npairs})":24s}{cc:>7.2f}{tc:>7.2f}{cc-tc:>+7.2f}'
              f'{ct:>5d}{tt:>5d}{ct-tt:>+7d}')
        print(f'\n  v2 vs v1 (clean pairs only):  cost {100*(tc-cc)/cc:+.0f}%   '
              f'turns {100*(tt-ct)/ct:+.0f}%   (negative = v2 saves)')
    else:
        print("  no outcome-matched pairs complete yet")

    if a.verbatim:
        pairs = []
        for lbl in order:
            g = by.get(lbl, {})
            ctrl = fetch_artifact(a.bucket, g["ctrl"]["exp"], g["ctrl"]["run_id"]) if "ctrl" in g else None
            treat = fetch_artifact(a.bucket, g["treat"]["exp"], g["treat"]["run_id"]) if "treat" in g else None
            pairs.append((lbl, ctrl, treat))
        with open(a.verbatim, "w") as f:
            f.write(render_verbatim(pairs))
        print(f"\n  verbatim artifacts written to {a.verbatim}")


if __name__ == "__main__":
    main()
