# meeting_briefing optimizations index

Greppable index of every cost optimization applied to this experiment. Each row maps a label to the files it touches, the line ranges, and a one-sentence rationale. Most inline edits are wrapped in `<!-- OPT:<label> -->` markers (markdown) or `# OPT:<label>` markers (python) so you can grep the source for the exact spots. Some edits are structural (e.g. a schema field or a whole-step rewrite) and carry no inline marker — for those, use the "Where" column to locate them.

The shared cost principle: keep the always-loaded main-agent context small. Load heavy reference on demand, cap re-read tokens, and scope validator output so the agent does not burn turns chasing phantom errors.

> **Discovery fold-in (PR #58):** under #58 the agent VERIFIES a caller-supplied `PARAMS.meetingDate` instead of DISCOVERING the next meeting, so there is no 60-day window / cadence-inference crawl. The channel 1–4 ladder, the publish-lag early-exit, and the agenda-platform reference live INLINE in instruction.md Step 2. The `publish-lag` and `channels-1-4` cost levers point at instruction.md Step 2.

| Label | Files | Where | Rationale |
|---|---|---|---|
| `OPT:publish-lag-5day` | instruction.md, attachments/qa_checks.py | Step 2 `PUBLISH_LAG_CUTOFF_DAYS` early-exit; `PUBLISH_LAG_CUTOFF_DAYS` | Far-out meetings rarely have a published packet, so the agent short-circuits after channel 1 instead of exhausting channels 2-4; cutoff tightened from 7 to 5 days. Constant must match between Step 2 and `qa_checks.py`. |
| `OPT:channels-1-4` | instruction.md, attachments/qa_checks.py | Step 2 ladder; `_REQUIRED_CHANNELS` | Retired the low-yield discovery channels (local news, clerk/records page, past-meeting URL probe) that produced ~1% of finds; ladder and validator required-set move together. Structural — no inline marker; locate via the Where column. |
| `OPT:reason-cap-280` | manifest.json | `run_decisions[].reason` (both schema branches) | Capped each run_decision reason at 280 chars; every reason token is re-read on later turns. |
| `OPT:lever2` | attachments/qa_checks.py, instruction.md | `validate_schema` / `_select_branch_schema`; Step 18 + "Early structural check" "use qa_checks, don't hand-roll" note | Branch-aware schema validation: `qa_checks.py` selects the single `oneOf` branch keyed on `briefing_status` and reports errors scoped to that branch, so the agent stops chasing phantom merged-oneOf errors. The instruction tells the agent to run `qa_checks.py` rather than hand-rolling `jsonschema` against the raw oneOf. Structural — no inline marker. |

## Invariants

- **Channel set**: any change to how many discovery channels are required is a paired edit to `instruction.md` Step 2 AND `qa_checks.py` `_REQUIRED_CHANNELS` in the same change. The validator rejects near-term `awaiting_agenda` artifacts that skip a required channel.
- **Publish-lag cutoff**: `PUBLISH_LAG_CUTOFF_DAYS` in `qa_checks.py` and the constant stated in `instruction.md` Step 2 must match.
- **Stale-schedule exemption**: under #58, a `no_meeting_found` artifact that records a `no_meeting_on_target_date` run-decision reason is exempt from the channel-depth check entirely (the agent verified the caller-supplied date and the platform showed no meeting). Keep `_STALE_SCHEDULE_REASONS` in `qa_checks.py` in sync with the reason string emitted by instruction.md Step 2.
