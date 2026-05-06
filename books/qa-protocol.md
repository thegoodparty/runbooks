Companion book for any generation run that produces an intelligence product — briefings, memos, reports, or production-candidate outputs.

## When to Invoke

Invoke this book in addition to the primary task book whenever a run:

- generates a briefing, memo, orientation document, or structured report
- synthesizes intelligence from multiple sources
- produces output intended for review, release, or comparison
- runs retrieval, scoring, or ranking that informs recommendations

Do not invoke for one-off queries, dashboards, or operational tasks that produce no durable artifact.

## Prerequisites

**Tools**: `uv`
**Scripts**: `scripts/python/qa_init.py`, `scripts/python/qa_validate.py`

## Before Generation

Run `qa_init.py` to scaffold the output folder:

```bash
cd scripts/python && uv run qa_init.py --product-id <id> --briefing-type <type>
```

This creates `output/` with stub files for all required artifacts. Populate those stubs during generation — do not reconstruct them afterward.

## Generation-Time Requirements

During generation, capture the following:

- **Sources**: every document, query result, or data source accessed — whether or not it appears in the final artifact
- **Source extracts**: the specific text, rows, or spans that support each claim
- **Claims**: every factual or material assertion made in the output
- **Unsupported claims**: claims where no supporting extract was found — flag these explicitly, do not silently include them
- **Modeled data**: any score, estimate, or prediction from a model — label it as modeled in the artifact
- **Assumptions**: inferences made beyond what sources directly state
- **Retrieval log**: queries, tool calls, and data lookups performed (captured in `audit_bundle.json`)

## Output Contract

After generation, `output/` must contain:

**Required**:

```
output/
  final_artifact.*        ← generated document (md, json, or pdf)
  audit_bundle.json       ← run metadata and index of all artifact paths
  sources.json            ← every source accessed
  claims.json             ← every factual claim with citation IDs
  qa_results.json         ← populated by qa_validate.py
```

**Recommended**:

```
output/
  source_snapshots/       ← captured text from web or PDF sources
    source_001.txt
  repair_plan.json        ← populated by qa_validate.py when needed
```

### audit_bundle.json

```json
{
  "product_id": "...",
  "briefing_type": "...",
  "run_timestamp": "...",
  "generator": "...",
  "final_artifact_path": "output/final_artifact.md",
  "sources_path": "output/sources.json",
  "claims_path": "output/claims.json",
  "qa_results_path": "output/qa_results.json",
  "final_status": null
}
```

### sources.json entry

```json
{
  "source_id": "source_001",
  "source_type": "government_record | official_budget | news | modeled | database_query | synthesis",
  "title": "...",
  "url": "...",
  "retrieved_at": "...",
  "retrieval_method": "web_fetch | database_query | tool_call | provided",
  "snapshot_path": "output/source_snapshots/source_001.txt"
}
```

### claims.json entry

```json
{
  "claim_id": "claim_001",
  "section_id": "...",
  "claim_text": "...",
  "claim_type": "budget_number | date_or_deadline | legal_identifier | named_person_or_role | vote_or_decision_fact | campaign_commitment | background_context | modeled_estimate | advice",
  "claim_weight": "high | medium | low",
  "citation_ids": ["source_001"],
  "source_extracts": [
    {
      "source_id": "source_001",
      "text": "...",
      "snapshot_path": "output/source_snapshots/source_001.txt"
    }
  ]
}
```

### Inline citations in the final artifact

Use `[source_id]` markers in the artifact text:

```markdown
The enacted FY2026 budget totals $32.1 billion [source_003].
```

Every inline marker must resolve to a `source_id` in `sources.json`. Do not use markers for decorative source lists — every marker must support a nearby factual claim.

## Pre-Output Checks

Before finalizing the artifact, verify:

1. **Relevance** — Does the output answer the actual user need? Is it tailored to the candidate, office, geography, and decision context?
2. **Grounding** — Are major claims supported by retrieved evidence? Are unsupported claims flagged or removed?
3. **Accuracy** — Are names, dates, numbers, offices, and policy facts correct? Are assumptions separated from facts?
4. **Actionability** — Does the output tell the user what to do, decide, or watch? Are recommendations realistic for the user's authority?
5. **Risk** — Could the output mislead an elected official or candidate? Does it present uncertainty where appropriate?
6. **Modeled data** — Is any modeled estimate labeled as modeled? Are model limitations noted where they influence recommendations?

## Gating

After generation, run the validator:

```bash
cd scripts/python && uv run qa_validate.py --output-dir output/
```

The validator populates `qa_results.json` and `repair_plan.json` (if needed), and prints a final status.

| Status | Meaning |
|---|---|
| `pass` | Safe to release. Only non-blocking annotations remain. |
| `regenerate` | A targeted section can likely be fixed by regenerating it. |
| `human_review` | Output may be useful but needs a person to resolve ambiguity or risk. |
| `block_release` | Do not release. Unsupported or incorrect material claim present. |

Routing priority (highest severity wins):

1. Any unsupported or incorrect high-weight claim → `block_release`
2. Any high-weight claim likely repairable by targeted regeneration → `regenerate`
3. Any unresolved medium-risk support issue → `human_review`
4. Only annotations remain → `pass`

## Post-Run Scoring

Score the output before marking a run complete. Required for any production candidate.

| Dimension | Score (1–5) | Notes |
|---|---|---|
| Relevance | | |
| Accuracy | | |
| Grounding | | |
| Actionability | | |
| Specificity | | |
| Risk Control | | |
| Product Fit | | |

Default thresholds for production candidates:

- Average ≥ 4.0
- No dimension below 3
- Accuracy and Grounding must each be ≥ 4

## Failure Modes to Watch

- Generic advice not tied to jurisdiction or candidate context
- Hallucinated local facts (names, amounts, dates)
- Unsupported prioritization or ranking
- Stale or irrelevant sources
- Modeled data presented as measured fact
- Overconfident language where uncertainty exists
- Outputs that sound good but cannot be audited afterward
