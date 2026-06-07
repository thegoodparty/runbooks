Autonomously derive a per-experiment **performance rubric** (the objective head of the eval) from an experiment's deployed runs, validate it, and measure it in real time against what is deployed in dev. Performance is objective — did the run produce an artifact, at what turns/cost/errors — so unlike the quality rubric this needs no cold judges, no human calibration, and no validity caveat. It is measurement, so it can run fully hands-off per experiment.

## What you get
- `experiment-evals/<exp>/perf.json` — the per-experiment performance config (status field, fail statuses, p95 cost/turns/error ceilings, no-artifact baseline). This is the "rubric."
- A real-time **PASS / FLAG / FAIL** gate over deployed dev runs via `scripts/python/perf_gate.py`.

## The one principle that shapes everything
There is **no universal status field**. meeting_briefing uses `briefing_status`, meeting_schedule uses `status`, opposition_research and opportunities_and_challenges have none. So:
- The only **universal** hard FAIL is **no artifact produced**. That signal is field-independent and applies to every experiment.
- Everything else is **per-experiment**: which status values mean failure (`fail_values`), and the cost/turns/error ceilings — a meeting_briefing run costs ~$3-10 while opportunities_and_challenges costs ~$0.20, so a single global threshold is meaningless. Derive them from each experiment's own distribution.

Performance ceilings can be **absolute today** (turns/cost/errors are facts); the quality rubric cannot, since quality validity needs a human referent. That asymmetry is why this gate can block now.

## Prerequisites
**books/.env variables**: `$AWS_PROFILE`, `$AWS_REGION`, `$ARTIFACTS_BUCKET` (resolved per env as `$ARTIFACTS_BUCKET-<env>`).
**Tools**: AWS CLI, `uv`. No agent/judge runtime needed — this is pure measurement.

## Step 1 — Derive the config from deployed dev runs
```bash
cd /path/to/runbooks
AWS_PROFILE=... AWS_REGION=... uv run scripts/python/derive_perf_thresholds.py <exp> --env dev -n 60
```
It samples ~`-n` deployed runs, pulls each trace + `artifact.json`, then:
- **discovers the status field** (scans artifacts for a `*status*` key; records it, or `None`),
- computes the cost/turns/error distribution over artifact-producing runs and sets **FLAG ceilings at p95**,
- sets `fail_values` to any observed status containing error/failed/failure, plus `"error"` by default whenever a status field exists (failures are rare, so a 60-run sample usually misses them),
- records the **no-artifact rate** as the failure baseline.

Output (evidence) lands in `outputs/perf-eval/<exp>/` (gitignored); the config is `outputs/perf-eval/<exp>/<exp>.perf.json`. Prefer `dev` so the rubric matches what you measure in real time; re-derive per env (a rubric from one env's runs is not guaranteed to fit another's cost profile).

## Step 2 — Validate the config (cheap, no humans)
```bash
uv run scripts/python/perf_gate.py outputs/perf-eval/<exp>/derive-dev/traces \
  --config outputs/perf-eval/<exp>/<exp>.perf.json --bucket $ARTIFACTS_BUCKET-dev
```
Confirm: the **status column reads real values** (e.g. `found`, not `None`/`NULL_STATUS` — a `None` for a no-status experiment is correct, but `None` where you expected a status means the wrong field was discovered); the FAILs are the no-artifact runs; FLAGs are the genuine top-of-distribution outliers, not the median. Then re-derive on a **fresh sample** and confirm the thresholds are stable (not fit to one batch's noise). `-n` of 50-60 is thin for a tail estimate; bump it for a load-bearing ceiling.

## Step 3 — Adopt
Graduate the validated config to the experiment's eval home, committed alongside the quality rubric:
```bash
cp outputs/perf-eval/<exp>/<exp>.perf.json experiment-evals/<exp>/perf.json
```

## Step 4 — Measure in real time against deployed dev
Dev run ids are UUIDv7 (time-ordered), so "latest N" is the newest deployed runs. Pull and gate on a cadence:
```bash
EXP=<exp>; B=$ARTIFACTS_BUCKET-dev; TD=outputs/perf-eval/$EXP/live; mkdir -p "$TD"
aws s3 ls "s3://$B/$EXP/" | grep PRE | sed -E 's#.*PRE (.*)/#\1#' | grep -E '^[0-9a-f]{8}-' \
  | sort | tail -30 \
  | xargs -P8 -I{} sh -c 'aws s3 cp "s3://'"$B"'/'"$EXP"'/{}/logs/workspace/conversation.jsonl" "'"$TD"'/{}.jsonl" --quiet 2>/dev/null || true'
uv run scripts/python/perf_gate.py "$TD" --config experiment-evals/$EXP/perf.json --bucket "$B"
```
Run it on a schedule (a `/loop`, a cron, or a launchd job). **Alarm** when the live no-artifact rate or FLAG rate drifts materially above the config's `no_artifact_rate` baseline — that is a regression in how the deployed agent is executing, independent of output quality.

## Step 5 — Gate prompt promotions on it
Before promoting an `instruction.md` change, run the gate on both arms per `books/evaluate-experiment-runs.md` Step 5: the treatment must add no new no-artifact FAILs and must not push runs over the ceilings the control stayed under.

## Troubleshooting
| Symptom | Cause -> fix |
|---|---|
| every run shows `status=None` | the experiment has no status field (fine — it's judged on artifact-presence + ceilings), OR the discovered field was wrong; check `status_counts` in the config |
| `n` far below `-n` | many sampled runs lack a trace/artifact (failed early); raise `-n`, or note the high no-artifact rate (it's a real signal) |
| ceilings look absurd (0 or huge) | too few artifact-producing runs in the sample; raise `-n` |
| derive finds 0 runs while scripting a loop | zsh does not word-split unquoted vars; call the script with explicit args, not a split loop variable |
