#!/usr/bin/env python3
"""Trajectory eval: score an agent run's *execution trace* (conversation.jsonl) —
how it worked (turns, cost, tool errors, planning overhead, redundancy), as
opposed to quality eval (cold-judge rubric, tallied by rubric_verdict.py) which scores the *artifact*.

Reads the trace the PMF runner uploads to
  s3://gp-agent-artifacts-<env>/<experiment>/<run_id>/logs/workspace/conversation.jsonl

Handles both trace dialects: the Fargate harness writes flat
`{"type":"tool_result"}` records; local Claude-Code runs nest tool results inside
`{"type":"user"}` records.

Usage:
  # one directory of *.jsonl traces -> per-run table + aggregate
  uv run python eval_trajectory.py <trace_dir>

  # A/B: two dirs, matched by filename -> control vs treatment with deltas
  uv run python eval_trajectory.py --ab <control_dir> <treatment_dir>

  # optional: pull a run's status from the trace for outcome-parity checks
  uv run python eval_trajectory.py <dir> --status-regex 'awaiting_agenda|briefing_ready|no_meeting_found'

  # optional: command-regex categories (e.g. meeting_briefing rules) for a
  # category breakdown beyond the built-in generic metrics
  uv run python eval_trajectory.py <dir> --rules meeting_briefing_eval_rules.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import Counter

PLANNING_TOOLS = {"TaskCreate", "TaskUpdate", "TaskStop", "TaskOutput", "TodoWrite"}


def _records(text: str):
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def parse_trace(text: str) -> dict:
    """Return {tool_calls:[(name,input)], tool_errors:int, num_turns, cost_usd}."""
    calls, n_err = [], 0
    num_turns = cost = None
    for rec in _records(text):
        t = rec.get("type")
        if t == "assistant":
            for b in rec.get("message", {}).get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    calls.append((b.get("name", ""), b.get("input") or {}))
        elif t == "tool_result":  # harness dialect
            if rec.get("is_error"):
                n_err += 1
        elif t == "user":  # CLI dialect
            for b in rec.get("message", {}).get("content", []) or []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    n_err += 1
        elif t == "result":
            num_turns = rec.get("num_turns", num_turns)
            cost = rec.get("total_cost_usd", cost)
    return {"calls": calls, "tool_errors": n_err, "num_turns": num_turns, "cost_usd": cost or 0.0}


def categorize(name: str, inp: dict, rules: list[dict]) -> str:
    if name in PLANNING_TOOLS:
        return "planning"
    blob = inp.get("command") or inp.get("query") or inp.get("url") or json.dumps(inp)
    for rule in rules:
        if re.search(rule["pattern"], blob):
            return rule["label"]
    return f"tool:{name}"


def exact_dup_count(calls) -> int:
    seen, dups = set(), 0
    for name, inp in calls:
        key = (name, json.dumps(inp, sort_keys=True, default=str))
        if key in seen:
            dups += 1
        else:
            seen.add(key)
    return dups


def score(text: str, rules: list[dict], status_regex: str | None) -> dict:
    p = parse_trace(text)
    cats = Counter(categorize(n, i, rules) for n, i in p["calls"])
    n = len(p["calls"])
    status = None
    if status_regex:
        m = re.findall(status_regex, text)
        status = m[-1] if m else None
    return {
        "turns": p["num_turns"],
        "steps": n,
        "cost": round(p["cost_usd"], 2),
        "tool_errors": p["tool_errors"],
        "exact_dups": exact_dup_count(p["calls"]),
        "planning": cats.get("planning", 0),
        "planning_pct": round(100 * cats.get("planning", 0) / n, 1) if n else 0.0,
        "status": status,
        "cats": dict(cats),
    }


def _load(path):
    return open(path, encoding="utf-8", errors="replace").read()


def run_dir(d: str, rules, status_regex):
    rows = {}
    for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
        rows[os.path.basename(f)[:-6]] = score(_load(f), rules, status_regex)
    return rows


def _print_table(rows: dict):
    hdr = f"{'run':28s}{'status':17s}{'turns':>6s}{'steps':>6s}{'cost':>7s}{'errs':>5s}{'dups':>5s}{'plan%':>6s}"
    print(hdr)
    print("-" * len(hdr))
    tt = ts = tc = 0
    for name, r in rows.items():
        print(f"{name[:28]:28s}{str(r['status'] or '-'):17s}{str(r['turns']):>6s}{r['steps']:>6d}"
              f"{r['cost']:>7.2f}{r['tool_errors']:>5d}{r['exact_dups']:>5d}{r['planning_pct']:>6.1f}")
        tt += r["turns"] or 0
        ts += r["steps"]
        tc += r["cost"]
    print("-" * len(hdr))
    print(f"{'TOTAL':28s}{'':17s}{tt:>6d}{ts:>6d}{tc:>7.2f}")
    return tt, ts, tc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("treatment_dir", nargs="?")
    ap.add_argument("--ab", action="store_true", help="A/B: dir=control, treatment_dir=treatment")
    ap.add_argument("--rules", help="JSON list of {pattern,label} command-category rules")
    ap.add_argument("--status-regex", help="regex; last match in the trace is the run's outcome")
    a = ap.parse_args()
    rules = json.load(open(a.rules)) if a.rules else []

    if a.ab:
        if not a.treatment_dir:
            ap.error("--ab requires control_dir AND treatment_dir")
        ctrl, treat = run_dir(a.dir, rules, a.status_regex), run_dir(a.treatment_dir, rules, a.status_regex)
        # match by trailing label after the last "__" if present, else full name
        def label(n):
            return n.split("__")[-1]
        cmap = {label(k): v for k, v in ctrl.items()}
        tmap = {label(k): v for k, v in treat.items()}
        keys = sorted(set(cmap) & set(tmap))
        print(f"{'input':16s}{'arm':6s}{'status':17s}{'turns':>6s}{'cost':>7s}{'plan%':>6s}{'errs':>5s}{'dups':>5s}")
        print("-" * 70)
        ct = tt = 0
        cc = tc = 0.0
        parity = True
        n_complete = 0
        for k in keys:
            c, t = cmap[k], tmap[k]
            print(f"{k[:16]:16s}{'ctrl':6s}{str(c['status'] or '-'):17s}{str(c['turns']):>6s}{c['cost']:>7.2f}{c['planning_pct']:>6.1f}{c['tool_errors']:>5d}{c['exact_dups']:>5d}")
            print(f"{'':16s}{'treat':6s}{str(t['status'] or '-'):17s}{str(t['turns']):>6s}{t['cost']:>7.2f}{t['planning_pct']:>6.1f}{t['tool_errors']:>5d}{t['exact_dups']:>5d}")
            if c["status"] != t["status"]:
                parity = False
                print(f"  !! OUTCOME MISMATCH for {k}: ctrl={c['status']} treat={t['status']} (comparison confounded)")
            # only aggregate inputs with a complete result record on BOTH arms
            if c["turns"] is None or t["turns"] is None:
                print(f"  !! INCOMPLETE for {k}: ctrl turns={c['turns']} treat turns={t['turns']} — excluded from totals")
            else:
                ct += c["turns"]
                tt += t["turns"]
                cc += c["cost"]
                tc += t["cost"]
                n_complete += 1
            print()
        print("=" * 70)
        print(f"complete paired inputs: {n_complete}/{len(keys)}")
        print(f"control   turns={ct:5d}  cost=${cc:6.2f}")
        print(f"treatment turns={tt:5d}  cost=${tc:6.2f}")
        if ct:
            print(f"delta     turns={100*(ct-tt)/ct:+.0f}% (negative = treatment worse)   cost={100*(cc-tc)/max(1e-9,cc):+.0f}%")
        print(f"outcome parity: {'OK (all inputs match)' if parity else 'BROKEN — fix before trusting the delta'}")
    else:
        rows = run_dir(a.dir, rules, a.status_regex)
        _print_table(rows)


if __name__ == "__main__":
    main()
