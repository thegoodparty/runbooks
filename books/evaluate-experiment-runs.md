Assess a PMF experiment's runs on two axes — **trajectory** (how the agent worked: turns, cost, errors, planning overhead, redundancy) and **quality** (how good the artifact is) — and A/B two prompt versions to check a change helps without regressing the measured quality axis.

Two evals, one harness. Both read what the runner already uploaded to S3, so assessing historical runs is free.

| Eval | Scores | Answers | Tool |
|------|--------|---------|------|
| **Trajectory** | the run's `conversation.jsonl` | *how did it work?* (turns, $, errors, repeats, planning %) | `scripts/python/eval_trajectory.py` |
| **Quality** | the artifact JSON | *is the output good?* | cold-judge **subagents** apply `experiment-evals/meeting_briefing/quality_rubric.md`, tallied by `scripts/python/rubric_verdict.py` |

## Prerequisites

**books/.env variables**: `$AWS_PROFILE` (`work`), `$AWS_REGION` (`us-west-2`)
**Tools**: AWS CLI, `uv`, and an agent runtime that can spawn subagents (the quality judges). No API key needed — the judges are cold subagents, not a script calling an LLM API.
**Where runs live**: `s3://gp-agent-artifacts-<env>/<experiment>/<run_id>/` →
  `logs/workspace/conversation.jsonl` (the trace) and `logs/workspace/output/<experiment>.json` (the artifact).

## Step 1 — Pull traces + artifacts for the runs you want to assess

```bash
EXP=meeting_briefing ENV=prod
mkdir -p /tmp/eval/traces /tmp/eval/artifacts

# A specific run, or a sample of recent runs (UUIDv7 prefixes are time-ordered):
RUN_IDS=$(AWS_PROFILE=work aws s3api list-objects-v2 --bucket gp-agent-artifacts-$ENV \
  --prefix "$EXP/" --delimiter "/" --query 'CommonPrefixes[].Prefix' --output text \
  | tr '\t' '\n' | sed "s#$EXP/##;s#/##" | grep -E '^[0-9a-f]{8}-[0-9a-f]{4}-' | sort | tail -20)

for rid in $RUN_IDS; do
  AWS_PROFILE=work aws s3 cp "s3://gp-agent-artifacts-$ENV/$EXP/$rid/logs/workspace/conversation.jsonl" \
    "/tmp/eval/traces/$rid.jsonl" --quiet 2>/dev/null
  AWS_PROFILE=work aws s3 cp "s3://gp-agent-artifacts-$ENV/$EXP/$rid/logs/workspace/output/$EXP.json" \
    "/tmp/eval/artifacts/$rid.json" --quiet 2>/dev/null
done
```

Traces carry no secrets in prod (the agent is broker-mediated, never holds keys); local-run traces can — don't vendor those.

## Step 2 — Trajectory eval

```bash
cd scripts/python
uv run python eval_trajectory.py /tmp/eval/traces \
  --status-regex 'awaiting_agenda|agenda_provided_by_user|briefing_ready|no_meeting_found|error' \
  --rules meeting_briefing_eval_rules.json
```

Per-run + aggregate: `turns`, `steps`, `cost`, `tool_errors`, `exact_dups` (verbatim-repeated calls), `planning_pct` (share of turns spent on `TaskCreate`/`TaskUpdate`/`TodoWrite` bookkeeping). The `--rules` file (a JSON list of `{pattern,label}` command-regexes) adds an experiment-specific category breakdown; omit it for tool-name-level metrics only. Reading: high `planning_pct`, `exact_dups`, or `tool_errors` are wasted-turn signals; trace each back to the instruction line that causes it.

## Step 3 — Quality eval (rubric, applied by cold-judge subagents)

Score each artifact against `experiment-evals/meeting_briefing/quality_rubric.md` using **cold-judge subagents**, not a script and not `qa_validate.py`. (`qa_validate.py` is a separate release-gate tool on a different axis — deterministic + `product_spec` triage — and is not the quality rubric.)

The rubric is graded by an LLM that never saw it being tuned (a *cold* judge), and you spawn **2+ judges per artifact** so the gap between them is your reliability signal. The judge does what a script can't reliably do here: read whether a packet carries real decision content (the eligibility/grounding gates) vs only titles.

1. **Spawn N cold judges per artifact** (2 is enough for a spread signal). Each subagent gets exactly two files and nothing else — the rubric and one artifact — with this directive:

   > Read ONLY these two files: the rubric `…/quality_rubric.md` and the briefing `…/<run_id>.json`. Apply the rubric exactly as written; you have never seen it before. Do not read any other file and do not show your work. Apply the rubric's Step-1 gates in order: if a gate disqualifies, output that gate's DQ verdict and stop; otherwise score every dimension 1-5 and produce **exactly the rubric's own output-format block** (the gate lines, each dimension's score with a one-line justification, and the total).

   Cold = a fresh subagent with no conversation history. Never let the judge read the validation log or other briefings (that contaminates it).

2. **Collect the blocks into a TSV** (`uuid	batch	judgeA	judgeB`; write `DQ` where a judge disqualified).

3. **Verdict:**
   ```bash
   # from repo root:
   uv run scripts/python/rubric_verdict.py experiment-evals/meeting_briefing/rubric_scores.tsv
   ```
   Prints a GO / NO-GO **reliability** verdict: graded inter-judge spread (must be ≤2), gate decisions reproducible (no 1-of-2 split), zero blowouts (spread ≥5). GO = reliable enough to gate prompt changes. It does **not** establish validity vs human truth — that needs an external referent (see the validation log's standing caveat).

## Step 4 — A/B two prompt versions (the optimization loop)

Treat the prompt as the **only** variable: clone the experiment to `<exp>_v2`, change only `instruction.md`, publish, dispatch the **same inputs** to both, and diff.

1. **Clone + edit + publish** (see `books/convert-runbook-to-experiment.md` for the dir layout):
   ```bash
   cd experiments && cp -r <exp> <exp>_v2
   # set "id":"<exp>_v2" in <exp>_v2/manifest.json; edit ONLY <exp>_v2/instruction.md
   cd ../scripts/python && uv run pytest test_experiment_manifests.py -q
   AWS_PROFILE=work uv run python publish_experiments.py --env=dev
   ```
2. **Dispatch the same inputs to both** experiments (see `books/run-pmf-experiment-cloud.md` for the SQS message shape). Use 3–10 inputs; for a fair test, pick inputs whose outcome is stable (e.g. for meeting_briefing, a `briefing_ready` input needs a meeting still in the future, or it falls back to `awaiting_agenda`).
3. **Collect both arms into two dirs** (`/tmp/eval/ctrl`, `/tmp/eval/treat`), filenames ending `__<input-label>.jsonl` so they match.
4. **Diff:**
   ```bash
   cd scripts/python
   uv run python eval_trajectory.py --ab /tmp/eval/ctrl /tmp/eval/treat \
     --rules meeting_briefing_eval_rules.json \
     --status-regex 'awaiting_agenda|agenda_provided_by_user|briefing_ready|no_meeting_found|error'
   ```
   It prints control-vs-treatment turns/cost/planning per input and an **outcome-parity check** — if any input lands a different `status` across arms, the comparison is confounded (the prompt changed *what* was produced, not just *how*), and the delta is meaningless until you fix it.
5. **Gate on quality.** A turn/cost win is only valid if quality holds. Run Step 3 (quality eval) on **both** arms' artifacts and confirm parity before promoting the v2 edits into the real experiment.

## Step 5 (optional, not required) — Fleet-wide waste discovery via embeddings

Steps 1–4 are the standard loop and need no embeddings. This step is a **possible extension**, not a dependency — skip it unless you're auditing hundreds of runs and want to find waste you didn't anticipate.

Deterministic `--rules` only catch categories you already know to look for. Embedding each step (`tool + normalized command`), clustering, and reading cluster **tightness** (mean intra-cluster cosine — high ≈ mechanically repeated, a cut candidate) plus within-run near-duplicate fraction surfaces *unanticipated* waste and semantic (not byte-identical) redundancy — which then feeds new `--rules` and prompt hypotheses back into Steps 2–4.

This is not wired into a script yet (it's a direction, not a turnkey command). If you build it, use only tooling this repo already ships — **no external/personal endpoints**:
- **`sentence-transformers`** (already in `scripts/python/pyproject.toml`) — runs a local model on CPU, no API key, works for everyone. Default choice.
- **Gemini embeddings** via `google-generativeai` + `GEMINI_API_KEY` (`scripts/.env`) — if you'd rather not download a local model.

Everything in Steps 1–4 works with zero embedding access.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `eval_trajectory.py` shows `turns: None` | trace has no `result` record (run was killed/truncated) — re-pull or treat steps as the turn proxy |
| A/B "OUTCOME MISMATCH" | the input's outcome isn't stable across arms — pick inputs whose result is deterministic, or the prompt change altered behavior (a quality question, not efficiency) |
| Quality judges disagree a lot (spread ≥5) | almost always a borderline empty-packet artifact straddling the eligibility gate — make empty-packet a gate (disqualify), not a scored cliff; confirm judges are reading the current rubric |
| A judge "shows its work" / verbose output | restate "do not show your work, output only the block"; cosmetic, doesn't affect the score |
| `briefing_ready` input fell back to `awaiting_agenda` on re-run | its meeting passed / agenda pulled — pick an input with a meeting still in the future |
