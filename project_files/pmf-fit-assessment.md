# Meeting Briefing → PMF Experiment: Fit Assessment

_Assessed 2026-05-10. Revisit after anatomy fix and first successful Haystaq run._

---

## Verdict

Not a clean drop-in, but the pattern maps. Medium-effort translation — not a rebuild. The right sequence is: prove the runbook works reliably on real data first, then translate. We are not there yet.

---

## What fits

**Haystaq via Databricks.** The broker auto-injects `WHERE Residence_Addresses_State` and `Residence_Addresses_City` — which is actually simpler than what the current instruction does manually. The query pattern maps directly to `pmf_runtime.databricks.connect()`. No change in logic, just different client.

**Web search for agenda platform discovery.** `WebSearch` works in Fargate. The agent's platform-discovery loop (Legistar → Granicus → eSCRIBE → city website) translates unchanged.

**HTTP page fetch for news and staff reports.** `pmf_runtime.http.get(url)` replaces curl. Response shape is a plain dict (`{"status", "headers", "body"}`) — not a `requests.Response` — so the instruction needs to use `r["body"]`, not `r.text`.

**PDF download.** `pmf_runtime.pdf.download(url)` replaces pdfplumber. Returns raw bytes; `pdftotext` extracts text. The instruction drops the local-file fallback entirely.

**Multi-step web + Databricks pattern.** This is exactly what PMF is designed for. Existing experiments do simpler versions of the same thing.

---

## Friction points

### 1. Local PDF path doesn't exist in Fargate

The current instruction accepts a `pdf` local file path in `params.json`. Fargate has no local filesystem for user-provided files. The experiment version must always discover the agenda URL via web search and fetch it via `pmf_runtime.pdf.download(url)` — the local shortcut is dropped entirely. This is actually better behavior (no manual file prep required) but the instruction needs to remove the `pdf` param and treat web discovery as the only path.

**Fix:** Remove `pdf` from `input_schema`. Add fallback to `agenda_url` param for cases where the URL is known in advance.

### 2. Multiple output files collapse to one artifact

The runbook currently writes four things: `briefing.json`, `claims.json`, `sources.json`, `source_snapshots/`. PMF captures only `/workspace/output/meeting_briefing.json`. Claims and sources must be embedded inline in the artifact or dropped. `source_snapshots/` has no equivalent — verbatim extracts live inside the artifact instead.

**Fix:** Design a single `artifact.json` schema that embeds priority issues, source citations, and (optionally) claims. The QA spine's multi-file contract does not apply in the PMF context.

### 3. Council member identity should come from params, not be discovered

The current instruction web-searches for a council member and picks one. In PMF, the official who triggered the run is the authenticated user — gp-api injects their name, district, and body into params before dispatch. This is a better personalization model but requires:
- `input_schema` to carry `official_name`, `official_district`, `body` fields
- gp-api to populate them from the user's profile at dispatch time
- The instruction to read identity from `PARAMS_JSON` rather than discovering it

**Fix:** Add identity fields to `input_schema`. Update instruction Step 1 to read from params rather than web-search.

### 4. The QA spine does not translate

PMF is single-agent-per-dispatch. The three-gate model (Gate 1 scaffold → generation agent → Gate 2 verification agent → Gate 3 validator) has no equivalent. In the experiment context:
- The output schema constraints in `manifest.json` are the proxy for Gate 1 and Gate 3
- `python3 /workspace/validate_output.py` (injected by the runner) is the proxy for Gate 3
- Gate 2 (separate verification agent) has no PMF equivalent

The QA spine remains useful as a local development and staff-use tool. It does not ship with the experiment.

### 5. Cost and turn budget at the high end

`district_issue_snapshot` runs in ~10 turns. The meeting briefing — platform discovery, PDF extraction, multiple staff report fetches, Haystaq queries across agenda items, news research per priority item, briefing assembly — would need:

| Field | Meeting briefing estimate | Typical experiment |
|-------|--------------------------|-------------------|
| `max_turns` | 100 | 35–60 |
| `timeout_seconds` | 3000 (50 min) | 600–1200 |
| Cost per run | $0.50–$1.50 | ~$0.30 |

Not a blocker, but worth knowing before scaling across many officials.

---

## Translation checklist (when ready)

- [ ] Prove runbook works reliably: anatomy matches reference, Haystaq data live
- [ ] Design `artifact.json` schema — single file, embeds priority issues + citations
- [ ] Define `input_schema`: `state`, `city`, `meeting_date`, `official_name`, `official_district`, `body`, optional `agenda_url`
- [ ] Rewrite instruction for `pmf_runtime` APIs: databricks, http.get, pdf.download
- [ ] Remove local PDF path; make web discovery the only agenda-fetch path
- [ ] Set `max_turns: 100`, `timeout_seconds: 3000`, `model: sonnet`
- [ ] Author spot-check rules (agenda date matches, priority items > 0, per-household math present)
- [ ] Validate manifest: `uv run pytest test_experiment_manifests.py`
- [ ] Publish to dev; dispatch test SQS message; tail logs; read artifact

---

## Prerequisites before translation

1. Briefing anatomy matches `city-council-member-briefing-copy.md` (talking points, action item, section headers, constituent sentiment no-data state)
2. Haystaq data appears correctly in at least one successful end-to-end run
3. gp-api confirmed willing to inject `official_name` / `official_district` / `body` at dispatch time
