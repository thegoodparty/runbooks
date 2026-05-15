# Meeting briefing v2 — stakeholder bundle

This branch is a focused snapshot of the GoodParty meeting briefing v2 work, prepared for stakeholder review across engineering, product, QA, and UX.

It contains the runbook (the prompt), a real example briefing artifact, the ported PMF experiment files, and the transparency record of how the runbook was translated into the experiment.

## Start here

Read **[`EXAMPLE_NOTES.md`](EXAMPLE_NOTES.md)** for the full reading guide — what's in the bundle, how to read it, known limitations, and what we're asking from each stakeholder group.

## Quick links

| What | Path |
|---|---|
| Reading guide | [`EXAMPLE_NOTES.md`](EXAMPLE_NOTES.md) |
| Runbook (the prompt) | [`books/run-meeting-briefing.md`](books/run-meeting-briefing.md) |
| Example artifact (real run output) | [`example_briefing_krishnan_nyc_d25_2026-05-14.json`](example_briefing_krishnan_nyc_d25_2026-05-14.json) |
| Audit trail from that run | [`example_briefing_krishnan_nyc_d25_2026-05-14.conversation-log.txt`](example_briefing_krishnan_nyc_d25_2026-05-14.conversation-log.txt) |
| PMF experiment manifest | [`experiments/meeting_briefing/manifest.json`](experiments/meeting_briefing/manifest.json) |
| PMF experiment instruction | [`experiments/meeting_briefing/instruction.md`](experiments/meeting_briefing/instruction.md) |
| Experiment validator + QA | [`experiments/meeting_briefing/validate_output.py`](experiments/meeting_briefing/validate_output.py) |
| Output JSON Schema (v2 contract) | [`scripts/python/meeting_briefing_output_schema.json`](scripts/python/meeting_briefing_output_schema.json) |
| Local-runbook validator + QA | [`scripts/python/validate_meeting_briefing.py`](scripts/python/validate_meeting_briefing.py) |
| Translation transparency report | [`translation_report.md`](translation_report.md) |
| Runbook → experiment converter (framework) | [`books/convert-runbook-to-experiment.md`](books/convert-runbook-to-experiment.md) |
| Runbook → experiment hints (domain-specific overlay) | [`books/translate-meeting-briefing-to-experiment.md`](books/translate-meeting-briefing-to-experiment.md) |

## Try it yourself

Validate the example artifact:

```bash
cd scripts/python
uv sync
uv run python validate_meeting_briefing.py ../../example_briefing_krishnan_nyc_d25_2026-05-14.json
```

Validate the experiment manifest against the meta-schema:

```bash
cd scripts/python
uv run pytest test_experiment_manifests.py -v
```

## Scope of this branch

This is a stakeholder-review snapshot — a curated subset of the full runbooks repo, focused on the meeting briefing experiment. The full repo (with all books, commands, scripts, and the other in-progress experiments) lives on `dev` / `qa` / `main`.
