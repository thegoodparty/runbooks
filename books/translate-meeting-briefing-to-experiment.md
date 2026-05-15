Translation hints for porting `books/run-meeting-briefing.md` into a PMF experiment at `experiments/meeting_briefing/`. Read this **in addition to** `books/convert-runbook-to-experiment.md` — that doc is the general framework; this one is the meeting-briefing-specific overlay.

## Prerequisites

**Required reading for the translation subagent:**
1. `books/convert-runbook-to-experiment.md` — the framework
2. `books/translate-meeting-briefing-to-experiment.md` — this doc (the hints)
3. `books/run-meeting-briefing.md` — the source runbook
4. `experiments/_schema/manifest.schema.json` — the meta-schema
5. `scripts/python/meeting_briefing_output_schema.json` — pre-staged output schema (embed verbatim)
6. `scripts/python/validate_meeting_briefing.py` — pre-staged validator (rename + relocate)

**Forbidden reading:**
- Any other experiment under `experiments/` (would contaminate naming and conventions)
- `experiments/.collin_reference/`
- Any prior translation attempt
- Any file under `.reference_docs/`

## Output contract

Produce three files in `experiments/meeting_briefing/`:

```
experiments/meeting_briefing/manifest.json
experiments/meeting_briefing/instruction.md
experiments/meeting_briefing/validate_output.py
```

Plus a `translation_report.md` in the working directory documenting every Step's source and whether the lift was verbatim or paraphrased.

## Pre-decided manifest config

Do not re-derive these. They are settled:

```json
{
  "$schema": "../_schema/manifest.schema.json",
  "id": "meeting_briefing",
  "version": 1,
  "model": "opus",
  "max_turns": 100,
  "timeout_seconds": 3000,
  "scope": {
    "allowed_tables": [
      "goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq",
      "goodparty_data_catalog.sandbox.haystaq_data_dictionary",
      "goodparty_data_catalog.private_samuel.district_top_issues_us_all"
    ],
    "max_rows": 50000
  }
}
```

**Notes on the config:**
- `model: opus` — the runbook's editorial work (tier classification, talking-points generation across 80+ items, source extract grounding) benefits from Opus reasoning. Confirmed by the local NYC pilot.
- `max_turns: 100` — the NYC run did this work in well under 100 turns; 100 is a comfortable ceiling.
- `timeout_seconds: 3000` — multi-step web + Databricks; 50 minutes is the right ceiling.
- `scope.max_rows: 50000` — the curated table queries return ~30 rows; the dictionary returns ~400 rows; L2 aggregation queries return 1 row; `information_schema.columns` for the L2 table returns ~300 rows. 50000 is comfortable.
- The `private_samuel.*` schema must be in `allowed_tables` for the broker to permit it. If the broker rejects it, fall back to dictionary-only mode (the runbook already handles this).

## input_schema

Lift from the `## Inputs` table in `books/run-meeting-briefing.md`. Required: `officialName`, `state`, `city`. Optional: `councilBody`, `l2DistrictType`, `l2DistrictName`, `meetingDate`, `agendaPacketUrl`, `agendaPdfPath`, `campaignUrl`. Encode types and patterns matching the runbook's documentation.

For `l2DistrictType` + `l2DistrictName`: use the `districtInputs` pattern from the meta-schema's `$defs`. The runbook treats both as optional (at-large officials don't have a sub-city district).

## output_schema

**Do not re-derive.** Embed `scripts/python/meeting_briefing_output_schema.json` verbatim into `manifest.json` under the `output_schema` key. The schema has been validated against a real run; you are not improving it during translation.

Strip the top-level `"$schema": "http://json-schema.org/draft-07/schema#"` from the embedded schema only if the meta-schema requires it stripped. Preserve everything else, including all `$defs`/`definitions` references.

## validate_output.py

Copy `scripts/python/validate_meeting_briefing.py` into `experiments/meeting_briefing/validate_output.py`. Rename the file but make minimal content changes:
- Update `SCHEMA_PATH` to load the schema from the manifest at runtime (the Fargate runner stages manifest.json into `/workspace/manifest.json`), OR keep loading from a sibling schema file if `validate_output.py` is co-located. Prefer the latter — simpler.
- Update `DEFAULT_ARTIFACT_PATH` from `/workspace/output/meeting_briefing.json` (already matches the convention).

The deterministic QA checks need no changes. They are product-agnostic enough to run against the artifact in either local-runbook or Fargate mode.

## Section-by-section map: runbook → instruction.md

`books/convert-runbook-to-experiment.md` Step 7 prescribes an instruction.md skeleton. Fill the skeleton this way.

### CRITICAL RULES block

Lift verbatim from the runbook's `about_the_agent.md` section (Role, Voice, Tone, Source discipline, Never fabricate, Verbosity) **plus** the Databricks + Web subsections of Step 8 from `convert-runbook-to-experiment.md`. Both are required:

- The runbook's content gives the agent the role and voice constraints, including the **Section-level posture overrides** table that authorizes directive voice for `talking_points`.
- The converter's broker quirks block gives the agent the platform-mechanics rules (state/city auto-injection, `Voters_Active='A'`, `hs_*` continuous scores, named placeholders, `pmf_runtime.http.get()` shape, etc.).

Do not paraphrase either. Both are short enough to lift wholesale.

### TODO CHECKLIST

Translate the runbook's `## Component sequence` into an ordered TODO list referencing the Steps below. Roughly:

1. Read PARAMS_JSON; verify Databricks env via a trivial `SELECT 1`.
2. Resolve the agenda source (path > URL > platform discovery).
3. Substantive-items check on the discovered agenda.
4. Chunk agenda PDF section-aware → page-fallback into `raw_context[]`.
5. Classify items into featured / queued / standard tiers.
6. Phase 1: cache curated district top issues table + data dictionary.
7. Phase 2: in-memory match per featured/queued item (curated → dictionary fallback → null).
8. Phase 3: batched AVG query against L2 for any dictionary-fallback items.
9. Per featured item: overview, talking points (5), recent news, budget impact.
10. Per queued item: overview, sentiment, recent news, budget impact. (No talking points required for queued.)
11. Compile claims with verbatim source extracts.
12. Compile sources with retrieved_text_or_snapshot.
13. Set briefing_status and required_data_points.
14. Write artifact to `/workspace/output/meeting_briefing.json`.
15. Run `python3 /workspace/validate_output.py`.
16. Spot-check.

### Steps section

| Step | Source in `books/run-meeting-briefing.md` | Lift |
|---|---|---|
| Step 1 — Read params + verify env | `runbook_header.md` pre-run setup check, params handling | Verbatim, including the SELECT 1 ping pattern |
| Step 2 — Resolve agenda source | `runbook_header.md` Inputs section (precedence rules) + `Sources.md` Agenda platform reference | Verbatim, full platform reference table including Legistar token-gating note and CivicClerk |
| Step 3 — Substantive-items check | `agenda_items.md` Substantive-items check section | Verbatim, including the placeholder item shape spec |
| Step 4 — Chunk agenda | `agenda_chunking.md` (full file) | Verbatim |
| Step 5 — Tier classification | `agenda_items.md` Tiers, Priority criteria, Featured selection sections | Verbatim |
| Step 6 — Cache Haystaq sources | `constituent_sentiment.md` Phase 1 — Cache the two sources upfront, including both SQL blocks and binding notes | Verbatim |
| Step 6b — Phase 1 gotchas | `constituent_sentiment.md` Phase 1 gotchas (permission denied, L2 district value format, abbreviated columns) | Verbatim |
| Step 7 — In-memory selection | `constituent_sentiment.md` Phase 2 | Verbatim |
| Step 8 — Batched fallback | `constituent_sentiment.md` Phase 3 with SQL | Verbatim |
| Step 9 — Per-item overview | `meeting_briefing.md` Briefing structure → Featured/queued items bullet for Overview | Translate to imperative |
| Step 10 — Talking points (featured only) | `talking_points.md` (full file, including posture override) | Verbatim |
| Step 11 — Recent news | `recent_news.md` (full file) | Verbatim |
| Step 12 — Budget impact | `budget_impact.md` (full file) | Verbatim |
| Step 13 — Compile claims | `Sources.md` Per-claim citation requirements + Source routing table | Verbatim |
| Step 14 — Compile sources | `Sources.md` Capture rules, Sub-documents, retrieved_text_or_snapshot requirements, URL rules | Verbatim |
| Step 15 — Set status + required_data_points | `agenda_items.md` substantive-items decision + `output_artifacts.md` briefing_status enum + `output_artifacts.md` required_data_points contract | Verbatim |
| Step 16 — Sentiment output formatting | `constituent_sentiment.md` Output section | Verbatim |
| Step 17 — Write artifact | Standard skeleton (`/workspace/output/meeting_briefing.json`) | Use converter skeleton |
| Step 18 — Validate | Standard skeleton (`python3 /workspace/validate_output.py`) | Use converter skeleton |

### Spot-check section

Translate the `## Conversation log discipline` section of `runbook_header.md` into a brief reminder, then add product-specific spot-check rules:

- `briefing_status` consistency: `briefing_ready` requires ≥1 featured item; `awaiting_agenda` requires `claims[]` empty.
- Every featured item must have at least one talking point.
- Every Haystaq score reported in `display.constituent_sentiment` must trace to either the curated table or the dictionary (haystaq_source must reflect which).
- If `private_samuel.district_top_issues_us_all` returned `INSUFFICIENT_PERMISSIONS`, `run_metadata.run_decisions[]` must include an entry for it.
- District-vs-city divergence: `district_note` populated only when both means are present **and** `abs(district_mean_score - city_mean_score) >= 10`.

### Failure modes table

Copy the table format from `convert-runbook-to-experiment.md` "Common failures." Add these meeting-briefing-specific rows:

- Symptom: `INSUFFICIENT_PERMISSIONS on private_samuel.district_top_issues_us_all`. Cause: Databricks principal lacks SELECT. Fix: log run_decision and fall back to dictionary-only mode (no run failure).
- Symptom: Legistar API returns 403 "Token is required." Cause: jurisdiction has gated their Granicus API. Fix: scrape `legistar.{client}.gov/Calendar.aspx` and related portal pages.
- Symptom: Phase 3 query returns NULLs for all city columns. Cause: dictionary column name is abbreviated and doesn't exist in L2. Fix: validate column names via `information_schema.columns` against the L2 table before running the AVG query.
- Symptom: District mean is suspiciously close to city mean. Cause: L2 district value format mismatch (e.g. `'25'` vs `'NEW YORK CITY CNCL DIST 25 (EST.)'`). Fix: discover the exact value via a `SELECT DISTINCT` query before binding.
- Symptom: `awaiting_agenda` placeholder item fails schema validation. Cause: agent invented a custom `tier_reason` string. Fix: use `["placeholder"]` exactly.

## Verbatim preservation rules for the subagent

Three rules to enforce on yourself during translation:

1. **If a runbook paragraph reads coherently as an instruction step, keep it verbatim.** Do not "instructionalize" prose that already reads as instructions. The runbook was written for an agent to follow; it is already in the right register.
2. **Lift entire prompt-component files when listed as "Verbatim" above.** Do not cherry-pick paragraphs and rewrite the transitions.
3. **When in doubt, lift verbatim and let the result be slightly long.** Per the converter doc: *"The shorter the instruction, the more the agent has to invent — and the more likely it'll invent something wrong. Long, opinionated instructions with copy-paste code blocks finish in fewer turns."*

## Translation report format

After producing the three files, write `translation_report.md` (in the working directory, not in `experiments/`) with this exact structure:

```markdown
# Translation report — meeting_briefing experiment

## Per-step source map

| Step in instruction.md | Source in run-meeting-briefing.md | Lift type | Notes |
|---|---|---|---|
| Step 1 | runbook_header.md ... | verbatim / paraphrased | (only if paraphrased: why) |
...

## Choices that required judgment

For every manifest field or instruction-section detail where you had to choose
and the hints doc / converter / runbook did not prescribe it, list:

- The field / detail
- The options considered
- The choice and the reason

## Gaps to flag back upstream

If anything in the runbook or hints doc was ambiguous, contradictory, or
missing, list it here. Each entry should be actionable feedback for the
hints doc or the runbook itself.
```

The report is the most important output. Read it before publishing. Every "had to guess" or "paraphrased because" entry is a signal to patch this hints doc or the runbook so the next translation is more mechanical.

## What NOT to do

- Do not run `pytest test_experiment_manifests.py`. The harness will run it after reviewing the report.
- Do not run `publish_experiments.py`. Publishing is a separate gated step.
- Do not modify `scripts/python/meeting_briefing_output_schema.json` or `scripts/python/validate_meeting_briefing.py`. If you find issues with them, list them in the report's "Gaps to flag back upstream" section.
- Do not invent new tier_reason values, claim_types, source_types, or briefing_status values. The enums in the schema are the canonical set; the runbook's tier_reason field is intentionally free-form but the preferred values listed in the schema description are sufficient — reuse them.
- Do not re-do the Haystaq SQL design. Phase 1 / Phase 2 / Phase 3 are settled. Lift them verbatim.
