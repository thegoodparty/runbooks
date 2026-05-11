# Project: Meeting Briefing + QA Spine

Session handoff for future agents and human collaborators. Captures current state, open issues, and how to pick up where we left off.

`project_files/` is gitignored — context only, never committed.

---

## Architecture (as built)

The pipeline is **agent-driven**. The executing agent IS the intelligence. There are no Python scripts that call an LLM for generation. `generate_meeting_briefing.py` existed briefly and was deleted — it was the wrong pattern for this repo.

```
params.json
    ↓ naive generation agent (books/instructions/meeting_briefing.md)
    — extracts agenda PDF via pdfplumber
    — queries Haystaq via databricks_query.py
    — researches local news, council dynamics, fiscal context
briefing.json + claims.json + sources.json + source_snapshots/
    ↓ briefing_to_pdf.py (no LLM calls)
briefing.md
```

For a QA-enabled run, three gates wrap the pipeline:

```
Gate 1: qa_init.py (scaffolds output dir)
    ↓ naive generation agent (same as above)
Gate 2: naive verification agent (books/instructions/inline_verify.md)
    — checks every source_extracts[].text verbatim against source_snapshots/
    — writes verification_report.json
Gate 3: qa_validate.py
    — schema → deterministic → Phase 1 LLM → Phase 2 LLM (if GEMINI_API_KEY set)
    — writes qa_bundle.json with Block/OK verdict
    ↓ briefing_to_pdf.py
briefing.md
```

---

## Branch status (as of 2026-05-10)

### `meeting-briefing`

| File | Purpose |
|------|---------|
| `commands/meeting-briefing.md` | Slash-command runbook — 3 steps only (setup, generate, render) |
| `books/instructions/meeting_briefing.md` | Agent instruction file — LLM-agnostic |
| `scripts/python/briefing_to_pdf.py` | JSON → Markdown renderer |
| `scripts/python/databricks_query.py` | Databricks SQL runner for Haystaq queries |

Recent commits:
- `8c2094c` — briefing_to_pdf resolves string source IDs from sources.json
- `806641a` (on qa-spine after merge) — databricks_query uses find_dotenv + correct var names

### `qa-spine`

`meeting-briefing` is already merged into `qa-spine`. Both branches are clean.

| File | Purpose |
|------|---------|
| `books/qa-spine.md` | Three-gate companion runbook |
| `books/instructions/inline_verify.md` | Gate 2 verification agent instruction — LLM-agnostic |
| `scripts/python/qa_init.py` | Gate 1 scaffolder |
| `scripts/python/qa_validate.py` | Gate 3 validator |
| `scripts/python/meeting_briefing_product_spec.json` | QA rules — single source of truth |

---

## Credentials

All live in `~/Research/.env`. `databricks_query.py` finds this automatically via `find_dotenv()`.

| Variable | Used by |
|----------|---------|
| `ANTHROPIC_API_KEY` | Gate 3 Phase 1 adjudication |
| `GEMINI_API_KEY` | Gate 3 Phase 2 escalation (skipped if absent) |
| `DATABRICKS_HOST` | Haystaq constituent data |
| `DATABRICKS_HTTP_PATH` | Haystaq constituent data |
| `DATABRICKS_TOKEN` | Haystaq constituent data |

Databricks connection confirmed working as of 2026-05-10. VPN (WireGuard) must be active.

---

## Experiment results so far

| Run | Branch | Output dir | Agent | Haystaq | QA verdict |
|-----|--------|-----------|-------|---------|------------|
| exp1 | qa-spine (old arch) | `exp1_alvin-TX_2026-04-16/` | Python script (deleted) | No | BLOCK |
| exp2 (gen only) | meeting-briefing | `exp2_alvin-TX_2026-04-16/` | Naive agent (Keko Moore) | No — creds not wired yet | n/a |
| exp2 (gen + QA) | qa-spine | `exp2_alvin-TX_2026-04-16_qa/` | Naive agent (Chris Vaughn) | No — creds not wired yet | OK (1 annotated) |

exp3 should be the first run with Haystaq live. Databricks creds are now wired correctly.

---

## Open issue: briefing anatomy does not match the reference

`project_files/city-council-member-briefing-copy.md` defines the expected output anatomy. The current renderer (`briefing_to_pdf.py`) and generation instruction (`meeting_briefing.md`) do not match it.

**Reference anatomy per agenda item:**

```
## Agenda Item: [Title]

### Overview
[2nd person narrative — "You're voting on..."]

### Constituent Sentiment
[% support / % oppose — or "No sentiment data yet for [item]"]

### Constituent Quote
[verbatim quote with constituent name — or "No constituent quote captured yet"]

### Budget Impact
[dollar amount + per-household breakdown]
[Source: ...]

### Talking Points
- [bullet naming council members, referencing prior votes]
- [bullet grounding in constituent data]
- [bullet on specific ask or watchout]

Was this summary helpful?
```

**Then a separate full-briefing deep-dive (one per item):**

```
# Full Briefing: [Title]
## Agenda Item
## Decisions You Are Being Asked To Make
## Why It Matters
## Talking Points For The Meeting
## Action Item
## Additional Context (expandable)
```

**Specific gaps to fix:**

1. **`briefing_to_pdf.py` does not render `talkingPoints` or `actionItem`** — both fields exist in briefing.json but the renderer ignores them. This is the most important fix.
2. **Section headers** — renderer uses `**bold labels**` instead of `### Section Name` headers.
3. **Constituent sentiment when unavailable** — reference shows "No sentiment data yet for [item]"; renderer omits the section entirely.
4. **Source citations placement** — renderer shows them inline per item; reference omits them from the card view.
5. **Constituent quote** — not in the schema at all. Generation instruction needs a `constituentQuote` field; renderer needs to display it.
6. **Two-section structure** — reference has a card summary + a full briefing deep-dive. Renderer produces only one merged view.

Fix order: (1) talking points + action item, (2) section headers, (3) sentiment no-data state, (4) constituent quote in schema + instruction + renderer, (5) two-section structure.

---

## How to run experiment 3 (first run with Haystaq)

**Test 1 — generation only (meeting-briefing branch):**

```bash
git checkout meeting-briefing
cd /Users/melecia/Research/runbooks/scripts/python

RUN_DIR=output/exp3_alvin-TX_2026-04-16
mkdir -p "$RUN_DIR/source_snapshots"

# Write params.json to $RUN_DIR (city: Alvin, state: TX, date: 2026-04-16,
# pdf: project_files/2026-04-16_agenda.pdf)

# Spawn naive generation agent with books/instructions/meeting_briefing.md

uv run python briefing_to_pdf.py \
  --briefing "$RUN_DIR/briefing.json" \
  --output "$RUN_DIR/briefing.md"
```

**Test 2 — generation + QA (qa-spine branch, meeting-briefing already merged):**

```bash
git checkout qa-spine
cd /Users/melecia/Research/runbooks/scripts/python

RUN_DIR=output/exp3_alvin-TX_2026-04-16_qa

# Gate 1
uv run python qa_init.py \
  --product-id alvin-TX_2026-04-16 \
  --briefing-type meeting_briefing \
  --output-dir "$RUN_DIR"

# Spawn naive generation agent with books/instructions/meeting_briefing.md

# Gate 2 — spawn naive verification agent with books/instructions/inline_verify.md

# Gate 3
uv run python qa_validate.py \
  --output-dir "$RUN_DIR" \
  --product-spec meeting_briefing_product_spec.json

uv run python briefing_to_pdf.py \
  --briefing "$RUN_DIR/briefing.json" \
  --output "$RUN_DIR/briefing.md"
```

---

## What to work on next session

1. **Fix `briefing_to_pdf.py`** — render talking points, action item, section headers, sentiment no-data state. Match reference anatomy.
2. **Add constituent quote to schema** — update `meeting_briefing.md` instruction to produce a `constituentQuote` field; update renderer to display it.
3. **Run experiment 3 with Haystaq live** — both test 1 and test 2. Review whether constituent sentiment appears correctly in the output.
4. **Evaluate full briefing / card separation** — decide whether the two-section structure (card + full briefing) should be in the Markdown render or is a UI-only concern.

---

## PMF experiment fit

See `project_files/pmf-fit-assessment.md` for a full assessment. Short version: the pattern maps, medium-effort translation, not ready yet. Prerequisites: anatomy fix, Haystaq live in a real run, gp-api confirmed on official identity params.

---

## Prior art

| Location | What it is |
|----------|-----------|
| `project_files/city-council-member-briefing-copy.md` | Reference output — anatomy and voice to match |
| `project_files/deliverable_1_meeting_briefing.md` | Generation rules spec — voice/register constraints |
| `project_files/deliverable_2_qa_spine.md` | QA spine design spec |
| `remotes/origin/runbook_qa` | Earlier QA spine attempt — claim taxonomy reference |
| `remotes/origin/add-meeting-briefing-runbook` | Original agent-driven architecture (pre-deletion) |
