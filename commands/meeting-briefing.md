<!-- v3 — 2026-05-09 -->

Generate a structured meeting briefing for an elected official from a city council agenda.

<!-- BEGIN: resolve-runbooks-dir -->
## Where this runs

This command can be invoked as `/meeting-briefing` (after `./install.sh`) or read
directly as `commands/meeting-briefing.md`. The scripts it references live inside
the runbooks repo. Set `$RUNBOOKS_DIR` to the repo root before running, or let the
fallback logic below resolve it.

```bash
# Option 1 — env var
export RUNBOOKS_DIR=/path/to/runbooks

# Option 2 — fallback: resolve from this file's location (agent use)
RUNBOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
```
<!-- END: resolve-runbooks-dir -->

## Prerequisites

**scripts/.env variables**: `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`
**Tools**: `uv` (Python runtime), WireGuard VPN connected (for Databricks access), `pdftotext` (for staff report extraction)
**Access**: Internet (for agenda platform discovery, news, and fiscal data)

## What this produces

| File | Description |
|------|-------------|
| `briefing.json` | Structured meeting briefing — priority items with talking points, constituent sentiment, sources |
| `claims.json` | Per-claim source extracts |
| `sources.json` | Source registry |
| `source_snapshots/` | Raw text from each source document (agenda, staff reports, Haystaq results) |
| `briefing.md` | Human-readable Markdown render |

---

## Steps

### 1. Set up the run directory

```bash
CITY=chapel-hill-NC            # lowercase city name + hyphen + 2-letter state code
DATE=2026-04-16                # meeting date YYYY-MM-DD
RUN_ID=output1                 # increment for each run: output1, output2, ...
RUN_DIR="$RUNBOOKS_DIR/scripts/python/output/${RUN_ID}_${CITY}_${DATE}"
mkdir -p "$RUN_DIR/source_snapshots"
```

Write `$RUN_DIR/params.json`:

```json
{
  "city": "Chapel Hill",
  "state": "NC",
  "officeName": "City Council",
  "citySlug": "chapel-hill-NC",
  "date": "2026-04-16",
  "pdf": "/optional/path/to/agenda.pdf"
}
```

The `pdf` field is optional. If omitted, the agent discovers the meeting platform and fetches the agenda directly.

### 2. Run the generation agent

Spawn an agent using `books/meeting-briefing-agent.md` as its instruction. Pass `$RUN_DIR` as the agent's workspace.

The agent will:
- Discover the council member and meeting platform
- Fetch the agenda and read staff report PDFs
- Query Haystaq for constituent sentiment (if Databricks credentials are set)
- Research local news, council dynamics, and fiscal data
- Write `briefing.json`, `claims.json`, `sources.json`, and `source_snapshots/`

### 3. Render the briefing

```bash
cd "$RUNBOOKS_DIR/scripts/python"
uv run python briefing_to_pdf.py \
  --briefing "$RUN_DIR/briefing.json" \
  --output "$RUN_DIR/briefing.md"
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Agent cannot find the agenda | City uses an unlisted platform | Provide `pdf` path in `params.json` as a fallback |
| Haystaq returns no results | VPN not connected or credentials not set | Connect WireGuard; add Databricks vars to `scripts/.env` |
| `pdftotext` not found | Tool not installed | `brew install poppler` (macOS) |
| Constituent data omitted | Databricks credentials absent | Expected — briefing generates without constituent sentiment |

---

## Output schema (`briefing.json`)

```
meeting.{title, date, citySlug, body, time}
executiveSummary.{totalAgendaItems, priorityItemCount}
priorityIssues[].{
  agendaItemTitle, itemNumber, actionType,
  detail.{whatIsHappening, whatDecision, whyItMatters, budgetImpact, whoIsPresenting},
  talkingPoints[],
  actionItem,
  sourceCitations[].{field, quote},
  constituentSentiment.{available, issue_label, aligned_voter_percentage, provenance_note}
}
constituentData.{available, provenance_note, voter_count, top_issues[]}
sources[]
```

## Known gaps

**Briefing anatomy does not match the reference design.** Specific fixes needed in priority order:

1. `briefing_to_pdf.py` does not render `talkingPoints` or `actionItem` — both fields exist in `briefing.json` but the renderer ignores them. Most important fix.
2. Section headers — renderer uses `**bold labels**` instead of `### Section Name` headers.
3. Constituent sentiment — renderer omits the section entirely when unavailable; it should show "No sentiment data yet for [item]."
4. Constituent quote — not in the schema or instruction at all. Needs a `constituentQuote` field added to both.
5. Two-section structure — the reference design has a card summary + full briefing deep-dive per item. The renderer produces one merged view.

**TODO: Fix `briefing_to_pdf.py`** — render talking points, action item, section headers, sentiment no-data state

**TODO: Add `constituentQuote`** to schema and instruction

**TODO: Run experiment 3 with live Haystaq data** — Databricks credentials are confirmed working (`DATABRICKS_HOST`, `DATABRICKS_TOKEN` resolved via `find_dotenv()`)

**TODO: District-level Haystaq scope** — add district type and name filters to the Haystaq query in the instruction; city-wide is the current default

**TODO: Legistar API direct integration** — agent currently discovers meeting platform via web search; a direct Legistar client would be more reliable for cities that use it

**TODO: OCR fallback** — `pdftotext` returns empty for scanned PDFs; the instruction should include a fallback path (`pdfplumber` is the working alternative)
