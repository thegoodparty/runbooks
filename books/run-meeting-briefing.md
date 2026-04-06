Run a PMF engine meeting briefing experiment for one or more cities, producing PDF reports.

## Prerequisites

**books/.env variables**: None
**scripts/.env variables**: None
**Tools**: Claude Code CLI, pandoc, xelatex — install via `bash scripts/shell/setup-macos.sh` (macOS) or `brew install pandoc texlive` directly. Avoid MacTeX — it requires a sudo pkg install.
**Access**: Internet (for Legistar, LINC, WebSearch, web scraping)

## Quick Start

To run a single city:

```
Run a meeting briefing for [City], [State] city council
```

To run multiple cities in parallel:

```
Run meeting briefings for Palestine TX, Westerville OH, Greenville NC, Greensboro NC city councils
```

## How It Works

Each briefing spawns an agent that:
1. Discovers a real council member via web search
2. Finds the city's legislative platform (Legistar, Granicus, eSCRIBE, CivicPlus, or web fallback)
3. Pulls the next meeting date and agenda (or projects from recent meetings if not yet posted)
4. Reads staff report PDFs when available
5. Pulls fiscal data (NC LINC API for NC, state-specific sources or web search for others)
6. Researches the official's campaign platform and committee assignments
7. Searches local news for agenda-relevant coverage
8. Generates a teaser email (150-200 words) and full governance briefing (1500-2500 words)
9. Self-scores against 12 quality dimensions (max 120)
10. Produces a JSON artifact with structured sources and inline citations

All outputs are saved to `outputs/` in this repo (gitignored).

## Steps

### 1. Create run directory and params

Each run gets a timestamped directory inside `outputs/`:

```bash
RUN_DIR="outputs/$(date +%Y%m%d-%H%M)-{city-slug}"
mkdir -p "$RUN_DIR"
```

Write `$RUN_DIR/params.json`:

```json
{
    "officeName": "City Council",
    "state": "XX",
    "city": "CityName",
    "county": "CountyName",
    "zip": "XXXXX"
}
```

**Do NOT fabricate `officialName` or `topIssues`** — the agent discovers these through research. Only provide city/state/county/zip and officeName (usually "City Council").

### 2. Spawn agents

Spawn one background agent per city. Each agent needs:
- The instruction file: `books/instructions/meeting_briefing.md`
- The params file: `$RUN_DIR/params.json`
- Workspace: `$RUN_DIR/` (replaces `/workspace/` in the instruction)
- Output: `$RUN_DIR/output/meeting_briefing.json`
- Mode: `auto` (needs Bash, Read, Write, WebSearch, WebFetch)

Agent prompt template:

```
You are running a meeting briefing experiment for a city council.

## Setup

1. Read the instruction from: books/instructions/meeting_briefing.md
2. Read your params from: $RUN_DIR/params.json
3. Your workspace is $RUN_DIR/. Wherever the instruction says /workspace/, use $RUN_DIR/ instead.
4. Write final output to $RUN_DIR/output/meeting_briefing.json

## Important

- The params do NOT include officialName or topIssues. Your FIRST task after reading params is to research the city council and discover a real council member to personalize the briefing for.
- The instruction has code blocks with placeholder variables like {client}, {eventId} — fill in with real values you discover.
- Make REAL API calls and web searches. Do not fabricate any data.
- Follow the full instruction including Step 0 (workspace setup, checklist, sources tracking) and all phase checkpoints.
- **Push hard on data collection.** Many city websites return 403 or have no API. When one source fails, try alternatives before marking a step done:
  - Fiscal: try the state auditor/comptroller website, ACFR (Annual Comprehensive Financial Report) PDFs, transparency portals, local news coverage of budget votes
  - Agenda: try Granicus, eSCRIBE, CivicPlus, Municode, then local newspaper meeting previews
  - Voting records: try local news coverage of contentious votes, even if there's no API
  - A step should only be marked "skipped" if 3+ different approaches have failed

Start now.
```

### 3. Monitor progress

Check checklist status across all runs:

```bash
for dir in outputs/*/; do
  name=$(basename "$dir")
  echo "=== $name ==="
  python3 -c "
import json
cl = json.load(open('${dir}checklist.json'))
done = sum(1 for s in cl['steps'] if s['status'] == 'done')
print(f'  {done}/15 steps done')
for s in cl['steps']:
    icon = '✓' if s['status'] == 'done' else '⏭' if s['status'] == 'skipped' else '·'
    print(f'  {icon} Step {s[\"step\"]:>3}: {s[\"notes\"][:80] if s[\"notes\"] else \"\"}')" 2>/dev/null || echo "  (not started)"
  echo
done
```

### 4. Review results

Parse output JSON:

```bash
python3 -c "
import json
d = json.load(open('$RUN_DIR/output/meeting_briefing.json'))
s = d['score']
print(f'Official: {d[\"eo\"][\"name\"]}')
print(f'Meeting: {d[\"meeting\"][\"body\"]} | {d[\"meeting\"][\"date\"]}')
print(f'Score: {s[\"total\"]}/{s[\"max\"]} | {s[\"recommendation\"]}')
print(f'Sources: {len(d.get(\"sources\", []))}')
print(f'Briefing: {len(d[\"briefing_content\"].split())} words')
"
```

### 5. Generate PDFs

Use `scripts/python/briefing_to_pdf.py` to convert each briefing JSON to PDF:

```bash
cd "$(git rev-parse --show-toplevel)/scripts" && uv run python/briefing_to_pdf.py $RUN_DIR/output/meeting_briefing.json $RUN_DIR/briefing.pdf
```

### 6. Verify artifacts

Each run directory should contain:

| File/Dir | Contents |
|----------|----------|
| `params.json` | Input parameters used |
| `output/meeting_briefing.json` | Full artifact (briefing, teaser, score, sources, agenda) |
| `briefing.pdf` | Formatted PDF for sharing |
| `checklist.json` | Step-by-step progress log |
| `sources.json` | All data sources accessed with URLs |
| `downloads/` | All downloaded files (PDFs, budget docs, agendas, staff reports) |
| `api_responses/` | Saved API responses (Legistar events, agenda items, fiscal data) |
| `instruction.md` | Copy of instruction the agent used (written by agent at Step 0) |
| `conversation.log` | Turn-by-turn log of every tool call, result, and decision |

## Expected Results

| City Size | Legistar? | Expected Score | Duration | Notes |
|-----------|-----------|----------------|----------|-------|
| Large (100k+) | Likely | 70-85 (send) | 15-25 min | Best results. Legistar + state APIs. |
| Medium (30-100k) | Maybe | 60-75 (review/send) | 20-30 min | Mixed. May find Granicus or eSCRIBE. |
| Small (<30k) | Unlikely | 55-70 (review) | 20-30 min | Web search fallback. Budget PDFs help. |

**Common weak dimensions:**
- Legislative Record (4-5): agenda often not published for future meetings
- Political Intelligence (3-5): most cities don't expose voting records in APIs

**Consistently strong dimensions:**
- Personal Tailoring (7-9): agent reliably finds official backgrounds and connects to agenda
- Fiscal Depth (7-9): strong when state APIs exist (NC LINC), weaker for web-search-only states

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Agent stuck on Step 2 | City has no discoverable platform | Agent should fall back to web_search. If stuck >5 min, check logs. |
| Checklist not updating | Some agents skip checklist writes | Known issue. Output may still be correct. |
| 403 on city website | Anti-bot blocking | Agent should fall back to news/web search. Less data but still functional. |
| 403 on `webapi.legistar.com/v1/{client}` | Some cities block the Legistar REST API even though they use Legistar | Fall back to the city's Legistar web interface (`{client}.legistar.com`) via WebFetch. The web UI is usually accessible when the API isn't. Confirmed for NYC; likely affects other large cities. |
| Spawned agent can't use Bash or read `/tmp/` | Subagent doesn't inherit parent session permissions | Run the briefing in the main session instead of spawning a background agent, or pre-approve Bash/Read/Write for the subagent before launching. |
| Score below 40 (hold) | Very small city, no data | Expected for tiny municipalities. Review the briefing manually. |
| Agent errors out | API overload or max turns | Re-run. Consider reducing scope (fewer news searches). |
