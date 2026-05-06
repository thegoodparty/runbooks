# Experiment QA Protocol

Use this book whenever running, reviewing, or comparing experiments that generate governance briefings, candidate guidance, campaign plans, summaries, or other LLM-authored outputs.

## Purpose

This protocol ensures generated outputs are:
- relevant to the user and task
- grounded in available evidence
- accurate and non-misleading
- actionable for the intended audience
- auditable after generation
- comparable across experiment runs

## When to Invoke

Invoke this book for:
- new prompt or model experiments
- briefing-generation runs
- rubric/scoring evaluations
- comparisons between output versions
- experiments that change retrieval, source selection, synthesis, tone, structure, or ranking
- any run intended to inform production behavior

Do not invoke for one-off casual drafting unless the output may later be evaluated or reused.

## Required Experiment Metadata

Each run must record:

- experiment name
- run ID
- date/time
- owner
- model/version
- prompt/template version
- retrieval configuration
- source corpus/version
- input user/candidate profile
- jurisdiction or geography
- output type
- intended audience
- success criteria
- known limitations

## Generation-Time Integrity Requirements

During generation, the system should preserve enough information to QA later.

For each output, capture:

- source documents used
- source snippets or spans used
- claims derived from each source
- unsupported claims
- assumptions made
- confidence level per major claim
- rejected or conflicting evidence
- retrieval queries used
- tool calls or data lookups performed
- intermediate outlines or planning artifacts, when useful
- final output version

## Evidence Ledger

Every generated briefing should have an evidence ledger.

Each ledger row should include:

| Output Claim | Source | Evidence Snippet | Transformation | Confidence | QA Notes |
|---|---|---|---|---|---|

Transformation examples:
- direct summary
- inferred implication
- prioritization/ranking
- recommendation
- extrapolation
- stylistic rewrite

Claims based on inference must be marked as inference.

## Pre-Output QA Checks

Before finalizing an output, check:

1. **Relevance**
   - Does the output answer the actual user need?
   - Is it tailored to the candidate, office, geography, and decision context?
   - Does it avoid generic civic advice?

2. **Grounding**
   - Are major claims supported by retrieved or provided evidence?
   - Are citations or evidence references available?
   - Are unsupported claims flagged or removed?

3. **Accuracy**
   - Are names, dates, offices, jurisdictions, numbers, and policy facts correct?
   - Are current facts checked against the freshest available source?
   - Are assumptions separated from facts?

4. **Actionability**
   - Does the output tell the user what to do, ask, decide, or watch?
   - Are recommendations realistic for the user’s authority?
   - Does it avoid overclaiming what the user can control?

5. **Risk**
   - Could the output mislead an elected official or candidate?
   - Could it create legal, political, reputational, or operational risk?
   - Does it present uncertainty where appropriate?

6. **Tone and Format**
   - Is the output concise, readable, and appropriately direct?
   - Does it match the product voice?
   - Is it structured for quick decision-making?

## Post-Run QA Scoring

Score each output using the briefing quality rubric.

Minimum dimensions:

| Dimension | Score | Notes |
|---|---:|---|
| Relevance | 1–5 |  |
| Accuracy | 1–5 |  |
| Grounding | 1–5 |  |
| Actionability | 1–5 |  |
| Specificity | 1–5 |  |
| Risk Control | 1–5 |  |
| Product Fit | 1–5 |  |

Outputs scoring below threshold must be labeled as non-shippable.

Suggested default threshold:
- Average score ≥ 4.0
- No critical dimension below 3
- Accuracy and grounding must each be ≥ 4 for production candidates

## Required QA Artifacts

Each experiment should output:

- final generated artifact
- experiment metadata
- evidence ledger
- retrieval log
- claim inventory
- rubric scores
- reviewer notes
- known failure modes
- recommendation: ship / revise / reject

## Failure Modes to Watch

Common failures:

- generic advice not tied to jurisdiction
- hallucinated local facts
- unsupported prioritization
- stale or irrelevant sources
- plausible but legally/politically risky recommendations
- confusing city authority vs staff authority
- overconfident language
- missing uncertainty
- weak “say this in the room” guidance
- outputs that sound good but cannot be audited

## Experiment Comparison

When comparing runs, evaluate:

- Which run has stronger factual grounding?
- Which run better uses local context?
- Which run is more actionable?
- Which run has fewer unsupported claims?
- Which run is easier to QA after the fact?
- Which run creates better reusable evidence artifacts?

Do not choose a winner based only on fluency.

## Recommended Generation Pattern

A high-integrity run should follow this sequence:

1. Load task and user context
2. Identify needed source types
3. Retrieve evidence
4. Build evidence ledger
5. Draft claim inventory
6. Generate output
7. Run pre-output QA checks
8. Revise output
9. Score with rubric
10. Save QA artifacts

## Output Contract

Every experiment run should produce a folder or object with:

```text
/run-id
  metadata.json
  final_output.md
  evidence_ledger.csv
  claim_inventory.md
  retrieval_log.json
  qa_scores.json
  reviewer_notes.md
  
  This book is not a standalone task book. It is an optional QA overlay. When invoked, apply its requirements in addition to the primary task book.