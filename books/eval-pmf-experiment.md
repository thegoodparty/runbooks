Evaluate a PMF engine experiment output for quality across structural, HTTP, and content dimensions.

## Prerequisites

**Tools**: Claude Code CLI (Opus model recommended for judge quality)
**Input**: A completed experiment run directory under `outputs/`

## Quick Start

```
Evaluate the district_intel output in outputs/20260408-1803-district_intel-westminster-co-opus-v2
Evaluate all district_intel outputs and compare across models
Evaluate the latest meeting_briefing output, skip HTTP checks
```

## Steps

### 1. Identify the run and load context

Read the output directory to determine:
- **Experiment type**: from the filename in `output/*.json` (e.g., `district_intel.json`)
- **Run metadata**: parse the directory name for model, version, city, state
- **Params**: read `$RUN_DIR/params.json`

Load the eval config from `books/pmf-engine/evals/{experiment}.eval.json`.

Load the output JSON from `$RUN_DIR/output/{experiment}.json`.

### 2. Extract cost metrics

Parse `$RUN_DIR/conversation.jsonl` — find the last line with `"type": "result"` and extract:
- `total_cost_usd`
- `num_turns`
- `duration_ms` (convert to seconds)

### 3. Run structural evaluations

For each dimension in the eval config's `structural` array, compute the metric:

| Metric | How to compute |
|--------|---------------|
| `value` | Read the field value directly |
| `array_length` | Count items in the array at path |
| `array_length_avg` | Average array length across parent items |
| `string_length` | Character count of the string at path |
| `string_length_avg` | Average string length across items |
| `numeric_avg` | Average of numeric values across items |
| `unique_values` | Count of distinct values at path |
| `unique_domains` | Count of distinct URL domains at path |
| `date_range_days` | Days between earliest and latest date at path |
| `field_completeness` | Fraction of listed paths that are non-empty |
| `citation_density` | Count of `[N]` markers across summaries / total summary chars |
| `citation_accuracy` | For each parent item: compare `[N]` markers in summary vs source IDs. Report orphan refs and unused sources |
| `url_liveness` | HEAD request each URL, report live/dead ratio |
| `custom` | Evaluate the expression in `check` |

Record each as `{id, value, type}` in the scores dict.

### 4. Run HTTP checks (optional)

For each dimension in the eval config's `http` array:
- Collect all URLs at the given path
- If `sample_size` is set, randomly sample that many URLs
- For each URL: make a HEAD request (or GET if HEAD fails), timeout 10s
- Record: `{value: live_ratio, total, live, dead_urls[]}`

Skip this step if the user says to skip HTTP checks or if running offline.

### 5. Run judge evaluations

For each dimension in the eval config's `judge` array:
- Read the relevant sections of the output JSON
- Evaluate against the dimension's `description`
- Assign a score from 1-5 with a brief justification

**Scoring rubric**:
- **5**: Excellent — fully meets the criterion, no issues
- **4**: Good — minor gaps that don't affect usability
- **3**: Acceptable — noticeable gaps but still useful
- **2**: Poor — significant issues that undermine quality
- **1**: Failing — criterion not met, output is unreliable for this dimension

### 6. Extract self-scores (meeting_briefing only)

If the eval config has `extract_self_scores`, read the agent's own scoring from `score.dimensions[]` and include as a separate section in the report.

### 7. Write eval report

Write `$RUN_DIR/eval_report.json`:

```json
{
  "eval_version": "1",
  "run_dir": "outputs/DIRNAME",
  "experiment": "district_intel",
  "model": "opus",
  "version": "v2",
  "city": "westminster",
  "state": "co",
  "evaluated_at": "ISO 8601",
  "layers_run": ["structural", "http", "judge"],
  "structural": {
    "issue_count": {"value": 6, "type": "count"},
    "citation_accuracy": {"value": 1.0, "type": "ratio", "detail": {"orphan_refs": 0, "unused_sources": 0}}
  },
  "cost": {
    "total_cost_usd": 1.64,
    "num_turns": 45,
    "duration_seconds": 360.0
  },
  "http": {
    "source_url_liveness": {"value": 0.92, "type": "ratio", "detail": {"total": 12, "live": 11, "dead": ["https://..."]}}
  },
  "judge": {
    "factual_grounding": {"score": 4, "justification": "..."},
    "segment_relevance": {"score": 5, "justification": "..."}
  },
  "self_scores": null,
  "warnings": []
}
```

### 8. Print summary

Print a markdown table summarizing the eval:

```
## Eval: district_intel — westminster, co (opus v2)

### Structural
| Dimension                  | Value |
|----------------------------|-------|
| issue_count                |     6 |
| avg_sources_per_issue      |  2.83 |
| citation_accuracy          |  1.00 |
| ...                        |   ... |

### Judge (1-5)
| Dimension                  | Score | Notes |
|----------------------------|-------|-------|
| factual_grounding          |   4   | ...   |
| segment_relevance          |   5   | ...   |
| ...                        |  ...  | ...   |

### Cost
| Metric           | Value  |
|------------------|--------|
| cost             | $1.64  |
| turns            |     45 |
| duration         |   360s |
```

## Comparing Across Models

When asked to compare multiple runs:

1. Find all `eval_report.json` files matching the filter (experiment, city, or glob)
2. Build a model x dimension matrix
3. Print as a comparison table:

```
## district_intel — westminster, co

| Dimension              | haiku-v2 | sonnet-v2 | opus-v2 |
|------------------------|----------|-----------|---------|
| issue_count            |        5 |         5 |       6 |
| avg_sources_per_issue  |     2.00 |      3.60 |    2.83 |
| citation_accuracy      |     1.00 |      1.00 |    1.00 |
| factual_grounding      |      3/5 |       4/5 |     4/5 |
| source_url_liveness    |     0.90 |      0.94 |    0.92 |

## Cost
| Model     | Cost   | Turns | Duration |
|-----------|--------|-------|----------|
| haiku-v2  |  $0.55 |    25 |    227s  |
| sonnet-v2 |  $1.53 |    42 |    387s  |
| opus-v2   |  $1.64 |    45 |    360s  |
```

## Spawning the Eval Agent

To run an eval from the parent runbook or CLI:

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
RUN_DIR="outputs/20260408-1803-district_intel-westminster-co-opus-v2"

cat <<PROMPT | claude -p \
  --allowedTools "Bash Read Write Glob Grep WebFetch" \
  --model opus
You are an eval agent. Follow the procedure in books/eval-pmf-experiment.md.

Evaluate the experiment output in $RUN_DIR.
Run all layers: structural, HTTP, and judge.
Write eval_report.json when done.
PROMPT
```

For batch comparison:

```bash
cat <<PROMPT | claude -p \
  --allowedTools "Bash Read Write Glob Grep WebFetch" \
  --model opus
You are an eval agent. Follow the procedure in books/eval-pmf-experiment.md.

Evaluate ALL district_intel outputs in outputs/ and compare across models.
Run structural and judge layers (skip HTTP).
Write eval_report.json for each, then print the comparison table.
PROMPT
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No conversation.jsonl | Cost metrics will be null — eval still runs |
| URL checks timing out | Skip HTTP layer or increase timeout |
| Output dir has no output/*.json | Experiment failed — nothing to eval |
| Multiple JSON files in output/ | Only eval the one matching the experiment name |
