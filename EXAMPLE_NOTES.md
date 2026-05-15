# Meeting briefing v2 — stakeholder bundle reading guide

This branch carries the complete v2 work-in-progress for the GoodParty meeting briefing pipeline. The bundle is meant for stakeholder review (engineering, product, QA, UX). It contains both the *runbook* form (a Claude Code agent reading a markdown procedure) and the *PMF experiment* form (a Fargate-runner agent reading a manifest + instruction). Both forms target the same JSON artifact contract.

## What's in the bundle

### The runbook (the prompt)

- **`books/run-meeting-briefing.md`** — the consolidated v2 runbook. Around 1,050 lines. This is the prompt a fresh Claude Code session reads to produce a briefing locally. It composes from prompt components: role/voice rules, agenda chunking strategy, item tiering rules, Haystaq sentiment workflow, news/budget/talking-points rules, source-citation rules, and the output JSON shape.

### Example run output (runbook form)

- **`example_briefing_krishnan_nyc_d25_2026-05-14.json`** — a real briefing artifact produced by the runbook for Council Member Shekar Krishnan, NYC City Council District 25, against the May 14 2026 NYC Stated Meeting.
  - 80 agenda items tiered: 3 featured, 12 queued, 65 standard
  - 10 claims with verbatim source extracts
  - 7 sources with `retrieved_text_or_snapshot` captured at fetch time
  - 6 `run_decisions` documenting the agent's judgment calls

- **`example_briefing_krishnan_nyc_d25_2026-05-14.conversation-log.txt`** — the audit trail from that run. Shows the agent's tool-call sequence and decisions, including the production-grade discoveries the run surfaced: NYC Legistar API now requires a token, `private_samuel.district_top_issues_us_all` permission-denied for the test principal, dictionary column names abbreviated vs L2's full names, NYC L2 district format `'NEW YORK CITY CNCL DIST 25 (EST.)'` not `'25'`.

### The PMF experiment files (Fargate form)

Produced by a translation pass from the runbook into the canonical PMF experiment shape:

- **`experiments/meeting_briefing/manifest.json`** — JSON manifest validated against `experiments/_schema/manifest.schema.json`. Carries `id`, `version`, `model: opus`, `max_turns: 100`, `timeout_seconds: 3000`, `scope.allowed_tables` listing the three Databricks tables, full `input_schema`, and the full `output_schema` (the v2 artifact contract embedded inline).
- **`experiments/meeting_briefing/instruction.md`** — agent prompt the Fargate runner stages alongside the manifest. Carries the same content as the runbook above, restructured into the canonical Steps + CRITICAL RULES + Spot-check + Failure modes skeleton.
- **`experiments/meeting_briefing/validate_output.py`** — schema validator + deterministic QA checks, runs inside the Fargate container after the agent finishes. Loads `output_schema` from the manifest at runtime; runs eight deterministic QA checks (cross-reference integrity, required-data-points coverage, tier-reason consistency, source-extract presence, etc.).

### Translation transparency

- **`translation_report.md`** — produced by the clean-context subagent that performed the runbook→experiment translation. Documents every Step's source, every lift type (verbatim vs paraphrased), the two judgment calls the subagent had to make, and five upstream gaps to patch before the next port. Stakeholders reviewing the bundle can see exactly which runbook prose landed in which Step of the instruction.

### Supporting infrastructure

- **`scripts/python/meeting_briefing_output_schema.json`** — the v2 output schema as a standalone file. Embedded verbatim into `experiments/meeting_briefing/manifest.json`'s `output_schema` field; kept as a sibling for the local runbook validator.
- **`scripts/python/validate_meeting_briefing.py`** — the local-runbook validator. Functionally equivalent to `experiments/meeting_briefing/validate_output.py`; loads the schema from the sibling JSON file rather than from a manifest.
- **`books/convert-runbook-to-experiment.md`** — the general framework for porting any locally-runnable runbook into a PMF experiment. Predates this work.
- **`books/translate-meeting-briefing-to-experiment.md`** — domain-specific overlay paired with the converter above. Section-by-section verbatim-lift map, pre-decided manifest config, required translation_report format.

## How to read the bundle

1. **Start with this file.** You're here.
2. **Read the runbook (`books/run-meeting-briefing.md`)** to understand the prompt and the JSON contract.
3. **Open the example artifact** (`example_briefing_krishnan_nyc_d25_2026-05-14.json`) alongside the runbook to see what real output looks like. Pair with the conversation log to see the agent's reasoning.
4. **Skim the translation report** to see how the runbook was ported to the PMF form.
5. **Open the manifest and instruction** in `experiments/meeting_briefing/` to see what the Fargate runner consumes.

### Running the validator yourself

```bash
cd scripts/python
uv run python validate_meeting_briefing.py ../../example_briefing_krishnan_nyc_d25_2026-05-14.json
```

You will see exactly **12 schema errors**, all the same pattern:

```
$['items'][N]['display']['talking_points']: [] is not valid under any of the given schemas
```

These are real, not idealized. The example artifact predates one runbook tightening that required `talking_points: null` (not `[]`) on queued items without directive bullets. The runbook now specifies `null`; the next run will produce a clean artifact. The 12 errors are isolated to this one field on the 12 queued items; the other ~1,040 schema rules — cross-reference integrity, source-extract substring presence, briefing_status consistency, required-data-points coverage — pass cleanly.

## Where this is in the path to production

```
[1] Local runbook proves the workflow            ✓ DONE — see runbook artifact + conversation log
[2] Port runbook → PMF experiment                ✓ DONE — see translation_report + experiments/meeting_briefing/
[3] Validate manifest, publish to dev S3         Next — uv run pytest test_experiment_manifests.py; AWS_PROFILE=work uv run python scripts/python/publish_experiments.py --env=dev
[4] Live SQS dispatch in dev (real Fargate run)  After publish
[5] Promote to prod                              After dev validation
```

## Known limitations to discuss with stakeholders

1. **Permission gap on `private_samuel.district_top_issues_us_all`.** The curated 68-issue table is in a private schema; the agent's Databricks principal in the test run did not have SELECT on it. The runbook handles this gracefully (falls back to dictionary-only mode), and the Krishnan example demonstrates this fallback path. For production runs we need to either grant the broker's IAM the appropriate role, or move the curated table to a shared schema.
2. **NYC Legistar API now token-gated.** Observed in the test run. The runbook's `Sources.md` documents a fallback to public-portal HTML scraping. Some other large-city Legistar installations may follow.
3. **Twelve `talking_points: []` schema violations in the example artifact.** Already noted above. Patched in the runbook; not patched retroactively in the artifact.
4. **Five process-doc gaps surfaced by the translation pass.** Documented in `translation_report.md` § "Gaps to flag back upstream." None block this work; all to be patched before the next runbook-to-experiment translation.

## Asks of stakeholders

- **Engineering:** review `manifest.json` against PMF runtime expectations, `validate_output.py` for runner integration, `instruction.md` for any conventions we've missed.
- **Product:** validate the briefing experience demonstrated by `example_briefing_krishnan_nyc_d25_2026-05-14.json` — tier distribution, talking-point style, sentiment framing.
- **QA:** review the deterministic checks in `validate_output.py` and `scripts/python/validate_meeting_briefing.py`. See `translation_report.md` for the eight check categories. Comment on where LLM-adjudicated QA (qa-spine pipeline) should layer in.
- **UX:** open the artifact in your renderer (if any) or read the `items[].display.*` fields directly. Comment on the field set, the labels (`mean_score` + `score_direction` vs `support_pct` + `oppose_pct`), and the awaiting-agenda / no-meeting-found render paths.
