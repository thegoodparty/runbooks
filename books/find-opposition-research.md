Produce the Opposition Research of a candidate's campaign plan — one record per opponent (party affiliation, incumbent status, a 2-3 sentence summary, up to 3 key facts, and vetted source URLs that each return HTTP 200). Output is a structured JSON artifact `{ "opponents": [...] }`, not markdown.

This is the source runbook — the human-runnable version of the workflow. Once stable, port it to a PMF experiment via `books/convert-runbook-to-experiment.md`. Naming: `find-opposition-research.md` → `experiments/opposition_research/`.

**Nothing in this workflow calls election-api.** gp-api fetches the election-api results once and provides them as injected context; the agent never calls election-api (or any internal API). This matches the experiment, where the Fargate runner is network-quarantined and cannot reach election-api at all.

**Two ways this runs:**
- **In the experiment (production):** gp-api injects every field into the dispatch params — the `user_*` identity fields plus `campaign_strategy_context` and `campaign_primary_strategy_context` (the election-api results it fetched). The agent reads those from `PARAMS_JSON`.
- **Locally (this runbook):** feed the same shape — an enriched record, or a test set of them. You do not call election-api here either; you start from the provided context and use web search.

The opponent list is the **union** of (a) the candidates already in the provided context and (b) names surfaced by web search (late filers, write-ins, independents the context misses). Web search ADDS or ENRICHES; it never removes a provided candidate.

## Prerequisites

**books/.env variables**: none.
**scripts/.env variables**: none.
**Tools**: web search; URL verification via `pmf_runtime.http.head` (in the experiment) or `scripts/python/verify_urls.py` (locally); `uv`; and the ability to spawn parallel subagents (Agent/Task) for the per-opponent research, with a sequential loop as the documented fallback. No `curl`/`election-api`/direct egress.
**Inputs (the injected contract)** — gp-api assembles these from its DB + the election-api results before dispatch; the agent just reads them:
- `race_id` — trace / idempotency identifier only; the agent does not reason over it and never looks anything up with it.
- `user_email`, `user_first_name`, `user_last_name`, `user_full_name`, `user_party_affiliation`, `other_party` — the candidate identity (output calls them "you", never by name; party resolves `Other` → `other_party`).
- `campaign_strategy_context` — the race roster + numbers (the election-api result) for the GENERAL election.
- `campaign_primary_strategy_context` — the PRIMARY stage's candidate roster only (`candidate_count` + `candidates`), or `null` when the race has no primary. All data is general-focused; the primary roster is provided in addition. Not every election has a primary, so this is often `null`.

**Output**: a JSON artifact `{ "opponents": [...] }` — one object per opponent, citations inlined, every cited URL verified 200. An uncontested race is `{ "opponents": [] }`. There is no markdown render step; gp-api renders the section from this JSON.

## What you need to know about the data

- **The provided context is the seed, web search is the supplement.** The candidates in the context are authoritative known filers but lag reality (late filers, write-ins, independents). Web search catches those. Every opponent carries a `source`: context candidates cite `GoodParty.org Data` (`source: "election-api"`), web-surfaced facts cite their URL (`source: "web"`).
- **All data is focused on the GENERAL election.** `campaign_primary_strategy_context` adds the PRIMARY stage's roster (candidates only) when one exists, else `null`. For offices that hold a primary, the primary roster is typically the real filed field while the GENERAL roster (`campaign_strategy_context.candidates`) is often empty. **So when `campaign_primary_strategy_context` is present, fold its `candidates[]` into the seed too** (excluding the candidate, deduping by fuzzy name). Both rosters are `source: "election-api"`.
- **`partisan_type`** is read from `campaign_strategy_context.partisan_type` (may be `null`); it only affects the party-affiliation line in the output. `nonpartisan` means party labels are registration noise.
- Treat obvious test/junk rows (placeholder names like "Jack Test", `@goodparty.org` / `+tag` emails) as not real — drop them.

## Steps

### 1. Get the assembled context and build the seed opponent list

**In the experiment:** read `campaign_strategy_context`, `campaign_primary_strategy_context`, and the `user_*` fields from `PARAMS_JSON`. No election-api call.

**Locally:** start from an enriched record (or a test set); read the same fields.

Identify the candidate via `is_user`: match `user_email` to `candidates[].email` (case-insensitive + trimmed), falling back to exact normalized `full_name`. The seed opponents are every OTHER candidate, drawn from BOTH `campaign_strategy_context.candidates` AND (when present) `campaign_primary_strategy_context.candidates`, deduped by fuzzy name and excluding the candidate. Each seed carries `first_name`, `last_name`, `full_name`, `party`, `is_incumbent`, `website_url`, `email`, `source: "election-api"`.

### 2. Discover late filers via web search and merge

Do discovery in ONE upfront pass, BEFORE researching anyone — AT MOST 2 WebSearch queries, then finalize the list:
- `candidates running for <office_name> <state> <election_date>`
- `<office_name> candidates <year>` (and a sample-ballot variant)

Prefer official sources: county/state board of elections, the clerk's sample ballot, Ballotpedia's race page, recent local race previews.

**The race must line up** — before adding any web-found name, confirm all three against an authoritative roster: same office (`candidate_office`, not just the same city or office type), same jurisdiction + `election_date`, and found on an authoritative roster. **Default-drop on ambiguity.** Hard cap: final list ≤ 20; web search may add AT MOST 3 names beyond the seed.

Keep ALL seed candidates even if web search finds nothing on them (web silence does not disconfirm a real filing; they route to "No public information found" in Step 5). If neither the seed nor web search finds any opponent other than the candidate, the race is uncontested — handle in Step 5.

### 3. Research each opponent (fan-out, one unit per opponent)

Per-opponent research is the slow part and the opponents are independent, so fan out: dispatch one research subagent per opponent (up to 20), all in one batch, then collect. Write the shared brief once to scratch and dispatch short per-opponent pointers; each unit writes its result to a fragment file and returns one line. **Sequential fallback:** if no subagent dispatch is available, loop the same per-opponent brief sequentially — identical output, only slower.

Each research unit, self-contained:
- Runs AT MOST 2 WebSearch queries for its one opponent (`"<full name>" <office_name> <state>` + a campaign/candidate variant). Pull the 2-3 sentence profile and up to 3 facts from the snippets; do not fetch pages just to extract facts.
- Never names the candidate you write for in its output.
- Source rules: prefer official government pages, major/local news, the candidate's own site, Wikipedia as secondary. Avoid aggregators, unsigned blogs, LLM-generated stubs, PR wires. Ground every fact; if nothing is findable, return `no_info: true`.
- Verifies every URL with `pmf_runtime.http.head(url)` (locally, `verify_urls.py`): drop any non-200, use `final_url` on redirect. NEVER `curl`/`wget`/`requests`/`urllib` — no egress, they hang. Drop LinkedIn URLs (they never verify for bots).
- If it cannot confirm the opponent in 1-2 searches, return `no_info: true` immediately — do not keep hunting.

Per-opponent return contract:
```json
{ "full_name": "Jane Doe", "party": "Democratic | Nonpartisan | null",
  "incumbent": "Yes | No | Unknown",
  "summary": "2-3 sentence profile grounded in verified sources",
  "facts": [{"text": "...", "source_label": "LAist", "url": "https://...200..."}],
  "websites": ["https://...200..."], "no_info": false }
```

### 4. Final URL audit

Trust the units — they already verified their URLs. Collect every cited URL, dedupe, verify each at most once with `http.head` only if you have a concrete reason to re-check. Drop any non-200 before assembling.

### 5. Assemble the structured artifact

Build `{ "opponents": [...] }`, one object per opponent in original order:
- `full_name` — as found.
- `party_affiliation` — `"Nonpartisan"` if `partisan_type` is `nonpartisan`; else the opponent's `party`; else `"Unknown"`.
- `incumbent` — `true` / `false` / `null` (from Yes / No / Unknown).
- `political_summary` — the 2-3 sentence summary; if `no_info`, `"No public information found as of <today's date>. You should conduct local research."`
- `key_facts` — up to 3 strings, each a fact with its citation inlined as `... ([source](url))`, 200-verified only.
- `websites` — campaign/social URLs only, each verified 200; may be empty.

An uncontested race is `{ "opponents": [] }`. Emit only this JSON — no markdown. Then validate against the output schema.

## Constraints (must follow)

- Plain, direct U.S. English. No em dashes. No jargon.
- Each `political_summary` / `key_facts` string is 1-3 sentences, grounded in what web search actually returned. Do not fabricate names, affiliations, or URLs.
- Never refer to the candidate by name in any opponent's text; the candidate is excluded from `opponents` entirely.
- Numbers, not words: "50% + 1", not "half".
- Be mindful of local election rules (North Dakota has no voter registration; Connecticut has no counties; California uses a top-two primary; Louisiana uses a jungle primary).
- Every cited URL must return HTTP 200.

## Output schema

The artifact validates against `experiments/opposition_research/manifest.json`'s `output_schema`. Shape:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["opponents"],
  "properties": {
    "opponents": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["full_name", "party_affiliation", "incumbent"],
        "properties": {
          "full_name": {"type": "string", "minLength": 1},
          "party_affiliation": {"type": "string", "description": "Party name, 'Nonpartisan', or 'Unknown'."},
          "incumbent": {"type": ["boolean", "null"]},
          "political_summary": {"type": "string"},
          "key_facts": {"type": "array", "items": {"type": "string", "minLength": 1}, "maxItems": 3},
          "websites": {"type": "array", "items": {"type": "string", "pattern": "^https?://"}}
        }
      }
    }
  }
}
```

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Run hangs ~30s on a URL | Used `urllib`/`curl`/`requests` | Verify with `pmf_runtime.http.head` only; never direct egress |
| A web "candidate" isn't really in this race | Wrong office/district, past cycle, or withdrew | Confirm office + jurisdiction + date on an authoritative roster; default-drop |
| Empty general roster, no opponents found | The general roster is often empty | Seed from `campaign_primary_strategy_context.candidates` too; then web search |
| A seed candidate has no web coverage | Web silence on a real filer | Keep them with the "No public information found" summary — never drop a real filing |
| LinkedIn URL returns 999/404 | LinkedIn blocks non-authenticated bots | Drop the citation |
| Candidate's own name appears in an opponent's text | Snippet mentioned both | Strip it; the candidate is never named and never in `opponents` |
