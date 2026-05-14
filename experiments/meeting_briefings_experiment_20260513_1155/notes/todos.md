# To-dos — meeting_briefings_experiment_20260513_1155

## Instruction fixes

1. **Step 5 — replace `information_schema` column discovery with data dictionary search**
   - Current: agent queries `information_schema` → gets 303 names → picks blindly → then consults dict
   - Fix: fetch all `hs_*` entries from `goodparty_data_catalog.sandbox.haystaq_data_dictionary` once before the per-item loop (returns `column_name`, `proper_column_name`, `description`, `score_high_means`, `complementary_field`). Filter in Python by keywords from the agenda item. Agent picks from a small candidate set with semantic context.
   - Why Python filtering not SQL LIKE: keywords are string-interpolated, avoids injection risk
   - Note: all 303 L2 `hs_*` columns have descriptions in the dict. One edge case: `hs_artificial_intelligence_concerned_raw` has description "AI" — agent should fall back to `proper_column_name` if description is < 5 chars.
   - If no candidates match: set `constituent_sentiment` to `null` — no guessing

2. **Step 5 — add city name casing rule + jurisdiction verification (Step 5.0)**
   - Problem: Databricks string comparison is case-sensitive. L2 uses title case (`'Alvin'`). The broker injects `PARAMS.city` verbatim — `'ALVIN'` or `'alvin'` return 0 rows with no error.
   - Fix A: Add to CRITICAL RULES — city names in L2 use title case; all-caps or lowercase returns 0 rows silently
   - Fix B: Add Step 5.0 (run once before the per-item loop) — query district count; if 0, skip all Haystaq lookups, set all `constituent_sentiment` to `null`, add `briefing.haystaq_status` with city mismatch message
   - Note: cross-state same-city confusion is already handled because the broker injects both state AND city

## QA

3. **Align experiment output schema with UI expected format**
   - UI format is in `notes/proposed_briefing_json_format.md`
   - Key mismatches identified (see that file for full table):
     - `priority_items` → `action_items`
     - `key_observations` → `talking_points` (also a product/voice decision — UI examples are advisory, experiment is intentionally neutral)
     - `constituent_sentiment` needs separate `summary` + `detail` fields; currently merged into one string
     - `recent_news` field renames: `headline → title`, `publication → outlet`; URL is embedded in UI vs referenced via source_id in experiment
     - `executive_summary` is an array of objects in experiment, a single boilerplate string in UI — needs product clarity
     - Sources: embedded per item in UI vs top-level array in experiment; `name → label`, `type → kind`, UI adds `icon_initial`
   - Open decision: does gp-api transform the artifact into the display shape, or does the experiment output the display-ready shape directly?
   - `claims` array is for QA only — should not appear in the display API response

4. **QA embedding — where do QA gates live in the PMF pipeline?**
   - Options mapped in earlier session: Tier 0 (self-QA in instruction), Tier 1 (qa_validate.py in Fargate container), Tier 2 (second chained job via broker)
   - Blocked on: can Fargate container reach Anthropic API from Python subprocess? Does broker support job chaining?
   - Action: get answers from PMF engine author (meeting was scheduled)

5. **Review output schema for QA layer requirements**
   - Does `claims` have enough structure for `qa_validate.py` to run its checks?
   - Is `source_snapshots` contract defined? (QA spine needs verbatim source text to verify claims)
   - Current schema has `source_extracts` on each claim — verify this is sufficient for Phase 1 QA

## 1447 experiment — instruction.md

7. **Write instruction.md for 1447** — currently a 3-line stub; needs full runbook content + PMF boilerplate + updated steps for the new output schema (no `briefing` wrapper, `constituent_sentiment` requires `haystaq_column` + `disclosure`, `recent_news` has `url` inline)

8. **Fix sentiment aggregation in Step 5** — data dictionary `aggregation_guidance` column specifies `AVG()` (mean score per district, 0–100 scale); score >60 = meaningful support lean, <40 = opposition lean. Run 1 used `SUM(CASE WHEN >= 50)` which is wrong. New `support_pct` = mean score, `oppose_pct` = 100 − mean score.

9. **Use data dictionary for column selection, not `information_schema`** — fetch all rows from `goodparty_data_dictionary` once, filter by agenda item keywords in Python, pass a short candidate list with `description` to the agent. Reduces blind picking from 303 columns. (Details in item 1 above.)

10. **Update run 2 dispatch params** — input param renamed `agendaUrl → agendaPacketUrl` in 1447 manifest. Add `campaignUrl` if testing campaign context.

## End-to-end

6. **Run the experiment as a full JSON artifact dispatch**
   - `notes/briefing_run1.md` is a markdown render from a local run, not a validated JSON artifact from the PMF dispatcher
   - Run via SQS dispatch against the April 16 2026 Alvin TX agenda
   - Validate output with `validate_output.py`
   - Check for Haystaq data (run1 had sentiment — confirm it used the right columns and the city matched)
