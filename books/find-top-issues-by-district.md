Find the most distinctive campaign issues in any L2 district by computing lift over the state baseline across a curated set of Haystaq issue scores, with optional thematic clustering.

## Prerequisites

**scripts/.env variables**: `DATABRICKS_API_KEY`, `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`
**Tools**: `uv`, Claude Code (for optional Tier 2 thematic clustering)
**Setup**: `cd scripts/python && uv sync`
**Inputs you provide**: a `(state, district_type, district_name)` triple. The caller is expected to know which district they want — this runbook does not resolve districts.

## What this does

For one `(state, district_type, district_name)` triple, this procedure produces a ranked list of distinctive campaign issues — the issues where the share of active voters scoring high (>=70 by default) is most elevated *relative to the rest of the state*.

Two tiers:

- **Tier 1 (deterministic)** — one Databricks query, returns top-K issues by `district_pct - state_pct` (lift in percentage points), deduped by topic. This is the script.
- **Tier 2 (optional, LLM)** — pass the Tier 1 top-15 to a Claude Code subagent that collapses correlated issues into themes, promotes the next-best distinct theme into freed slots, and returns top-5 with theme labels and a one-line district summary.

## The data

Single source table: `goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq` — joined L2 voter file plus all `hs_*` Haystaq score columns nationwide.

Three rules to internalize:

1. **Always filter `Voters_Active = 'A'`** — non-active rows are inactive registrations (moved, deceased, removed) and pollute baselines.
2. **`hs_*` are continuous 0–100 scores**, not flags. Threshold them (default `>= 70`) before averaging into a percentage.
3. **District name must match exactly** as stored in the L2 column — capitalization, suffix words, and number formatting all matter. If the script returns zero rows, the value didn't match. See the optional "Don't know the exact L2 string?" tip below.

### Don't know the exact L2 string?

Most callers already have a resolved district. If you don't, list candidates straight from L2 (no VPN, no extra creds — same connection as the rest of this runbook):

```bash
cd scripts/python
uv run databricks_query.py "
SELECT DISTINCT \`City_Ward\` AS district_name
FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq
WHERE state_postal_code = 'NC'
  AND Voters_Active = 'A'
  AND \`City_Ward\` ILIKE '%FAYETTEVILLE%'
ORDER BY district_name
"
```

Swap `City_Ward` for whichever L2 district column you're targeting and the `ILIKE` pattern for your search hint.

## Curated issue columns

Of the ~303 `hs_*` columns, only 106 are useful for "what does this district care about" framing. The curated list lives in `scripts/python/data/curated_issue_columns.csv` with fields:

| Field | Meaning |
|---|---|
| `column` | Exact `hs_*` column name |
| `topic` | Slug grouping correlated columns (e.g. `climate_change`, `abortion`) — used for dedup |
| `polarity` | `positive` / `negative` — direction of the score |
| `human_label` | Human-readable label for output |
| `keep` | `true` for the 106 keepers, `false` for dropped (with `drop_reason`) |

Excluded: turnout/likelihood scores, candidate-sentiment columns, demographic predictors, vague worldview signals. Curation is stable — do not re-derive.

## Steps

### Step 1 — Tier 1: lift aggregation

```bash
cd scripts/python
uv run find_top_issues_by_district.py \
  --state NC \
  --district-type US_Congressional_District \
  --district-name 12 \
  --top-k 15 \
  --output /tmp/nc12-top-issues.csv
```

Args:

| Arg | Default | Notes |
|---|---|---|
| `--state` | required | Two-letter postal code, e.g. `NC` |
| `--district-type` | required | L2 column name. Common: `US_Congressional_District`, `State_Senate_District`, `State_House_District`, `City_Council`, `Mayor`, `County` |
| `--district-name` | required | Exact value as stored in L2 (provided by caller, or look up via the tip above) |
| `--top-k` | 15 | How many ranked issues to print |
| `--threshold` | 70 | Score cutoff for "high-scoring voter" |
| `--output` | — | Optional path for the long-format CSV (all 106 columns × this district) |

The script:

1. Loads the 106 curated columns from `data/curated_issue_columns.csv`.
2. Issues one query: state baseline (active voters in the state, any non-null district) and district-specific percentages, both at the same `>=70` threshold, joined into one row.
3. Computes `lift_pct_pts = district_pct - state_pct` for each curated column.
4. Dedups by `topic` (keeps the highest-lift representative), prints top-K to stdout.
5. If `--output` is given, writes the full long-format CSV (all 106 rows) for downstream Tier 2 use.

Expected runtime: 30–90s for one district.

### Step 2 (optional) — Tier 2: thematic clustering via Claude

The deterministic top-15 often contains correlated issues — e.g. `climate_change`, `pipeline_fracking`, and `green_new_deal` all light up together in a progressive district. To collapse correlations and surface five genuinely distinct themes, hand the top-15 (with topic + polarity + label + lift) to a Claude Code subagent with this directive:

> You are given a district's top-15 distinctive issues by lift. Group correlated topics into themes (e.g. climate + EV + fracking → one "environment" theme). Promote the next-best distinct theme from below the top 15 if a slot opens. Return JSON with `district`, one-line `summary`, and `top5_themed` — each entry has `rank`, `theme`, `primary_label`, `primary_lift`, `primary_topic`, `supporting_topics` (merged into this theme), and `rationale`. Also return `merged_topics` and `promoted_from_below_top5`.

Run from the long-format CSV produced in Step 1:

```python
import csv, json
rows = list(csv.DictReader(open("/tmp/nc12-top-issues.csv")))
by_topic = {}
for r in sorted(rows, key=lambda x: -float(x["lift_pct_pts"])):
    if r["topic"] not in by_topic:
        by_topic[r["topic"]] = r
top15 = sorted(by_topic.values(), key=lambda x: -float(x["lift_pct_pts"]))[:15]
payload = [{"rank": i+1, "lift_pct_pts": float(r["lift_pct_pts"]),
            "topic": r["topic"], "polarity": r["polarity"], "label": r["human_label"]}
           for i, r in enumerate(top15)]
print(json.dumps(payload, indent=2))
```

Pipe `payload` plus the directive above into a Claude Code subagent. Save the JSON response.

## Example output (Tier 1)

```
=== Top 15 distinctive issues — NC × US_Congressional_District = 12 (487,213 active voters) ===

   +27.6  Government has role in affordable housing        (affordable_housing)
   +25.6  Distrusts police                                 (police_trust)
   +25.5  Medicare for All support                         (medicare_for_all)
   +24.6  Free community college support                   (free_community_college)
   +24.5  Work with China                                  (china_foreign_policy)
   +21.9  Minimum wage increase support                    (minimum_wage)
   ...
```

After Tier 2 (abbreviated):

```json
{
  "district": "NC-12",
  "summary": "Charlotte-urban progressive district with strong economic-populist majorities on housing, healthcare, education, and worker protections.",
  "top5_themed": [
    { "rank": 1, "theme": "Affordable housing & cost of living",
      "primary_label": "Government has role in affordable housing", "primary_lift": 27.57,
      "primary_topic": "affordable_housing",
      "supporting_topics": ["minimum_wage", "income_inequality", "family_medical_leave"] },
    ...
  ]
}
```

## Troubleshooting

| Failure | Fix |
|---|---|
| Script exits 2: "No rows returned" | District name doesn't match L2's spelling. Use the "Don't know the exact L2 string?" tip above to list real values; check capitalization, leading zeros, and string vs. numeric form. |
| All lifts within ±1 pct pt | District is genuinely centrist relative to the state, OR district sample is small (<2k active voters) and noise dominates signal. Check `district_total` printed in the header. |
| `Voters_Active` filter drops too much | Confirm with a raw `SELECT COUNT(*)` — for some states <60% of registered voters are `Voters_Active = 'A'`. That's expected; it's still the right filter. |
| Top results are all the same topic | The dedup by `topic` slug failed because two columns share a topic in `curated_issue_columns.csv`. Audit the CSV — `topic` should be unique per "thing the district cares about", not per column. |
| `databricks.sql` connection error | `scripts/.env` missing `DATABRICKS_*` vars. See `books/query-voter-data.md`. |
| `state_total` is unexpectedly low | The state's nationwide table partition may be partially loaded. Sanity-check with `SELECT COUNT(*) FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq WHERE state_postal_code='NC' AND Voters_Active='A'`. |

## Notes

- This procedure is a more principled approach than ad-hoc per-suffix issue-score scanning: a curated column universe replaces regex on column names, and lift over state baseline replaces raw averages so that "everyone in the state cares about X" doesn't dominate the output.
- Reusable across all states and L2 district types — only the curated CSV is shared, the query parameterizes everything else.
- Tier 1 is fully deterministic and reproducible; Tier 2 is LLM-assisted and should be re-run if the underlying curation changes.
- **Lift magnitude is itself signal.** A district where every issue's lift sits within ±5pp is genuinely centrist/swing — not broken. Districts with double-digit lifts on multiple themes are politically polarized. Compare the top lifts to gauge how distinctive the district really is.
