# Opposition Research

Produce a strategic `### Opposition Research` section for a candidate's campaign plan: the opponents in the race, party affiliation, incumbent status, a 2-3 sentence summary, and vetted source URLs (every URL returns HTTP 200). You combine two signals: the candidate roster inside the `campaign_strategy_context` handed to you in params (gp-api hydrated it from election-api before dispatch) and live web search, which catches late filers, write-ins, and independents the roster misses.

## BEFORE YOU START
1. Read this entire instruction end-to-end before executing anything.
2. Maintain a TodoWrite list mirroring the TODO CHECKLIST below.
3. Your params are in the `PARAMS_JSON` env var. Read them once at the top.
4. Write the final artifact to `/workspace/output/opposition_research.json` and nowhere else.
5. Run `python3 /workspace/validate_output.py` before declaring success.
6. Perform the spot-check at the bottom. Validator-passing data can still be garbage.

## TODO CHECKLIST
1. Read `PARAMS_JSON`; identify the candidate (`is_user`) and build the seed opponent list (Step 0).
2. Web-search to discover late filers and merge them into the opponent list (Step 1).
3. Finalize the opponent set — every non-self opponent (Step 2).
4. Research each opponent as an independent research unit (Step 3, the fan-out).
5. Final URL audit across every cited URL (Step 4).
6. Assemble the exact markdown section (Step 5).
7. Write `/workspace/output/opposition_research.json` and validate.

## CRITICAL RULES
- **Web access escalation ladder — cheapest tool that answers the question, in this order. Do NOT jump straight to the browser.**
  1. **`WebSearch`** (free, fast) — discover candidates, URLs, and facts. The result snippets are often enough on their own; only fetch a page when you need to confirm a specific claim against its body.
  2. **`pmf_runtime.http.head(url)`** — VERIFY a URL is live before citing it. This is a plain, non-browser status check (no Chromium render) and is the default for verification. Returns a plain dict `{"status": int, "final_url": str}` — use `r["status"]`, drop the URL if it is not 200, and cite `r["final_url"]` if it redirected.
     ```python
     from pmf_runtime import http
     r = http.head("https://example.com/article")   # {"status": 200, "final_url": "https://..."}
     if r["status"] != 200:
         pass  # not 200 -> see escalation below
     ```
  3. **`pmf_runtime.http.get(url)`** — the **browser render (Chromium), LAST RESORT.** Use it only when (a) `head` returned **403/405** on a site you believe is real (Cloudflare-style bot protection a bare request can't pass — the browser defeats it), or (b) you must read the page **body** to confirm a claim. `get` returns `{"status", "body", "source_url", ...}`; use `r["status"]`/`r["source_url"]`, never `.status_code`. It is ~100x slower than `head`, so reserve it.
- **Never use `WebFetch`** — the runner's quarantined network can't reach its domain-safety check; it always fails. Discover with `WebSearch`, verify with `http.head`, render with `http.get` only when forced.
- **Never make a direct network call from Python or the shell** — `urllib`/`urllib.request.urlopen`, `requests`, `httpx`, `curl`, `wget`, raw `socket`. The container has NO egress; these do not fail fast, they **HANG ~30s+ each and burn the time budget**. The ONLY way to reach a URL is `pmf_runtime.http.head` / `.get` / `.download` (broker-proxied). If you catch yourself importing `urllib` or `requests`, STOP and use `pmf_runtime.http`.
- **Do NOT call election-api or any other internal API.** The runner has no direct internet egress and cannot reach election-api. The candidate roster is already in `PARAMS.campaign_strategy_context.candidates` (you derive the opponent list from it in Step 0). Web search + `pmf_runtime.http` are your only outside-world tools.
- **The only PUBLISHED artifact is `/workspace/output/opposition_research.json`.** The runner publishes nothing else. You may write intermediate per-opponent fragments to `/workspace/scratch/` (see Step 3) — that directory is scratch space, never published.
- **Run `python3 /workspace/validate_output.py` before declaring success.** In-loop validation lets you fix violations cheaply; the runner-level validator rejects the artifact post-hoc if you skip it.

## Steps

### Step 0 — Read params, identify the candidate, derive the race shape

Read `PARAMS_JSON` once. Throughout this instruction: the candidate you write FOR is `user_full_name` (output calls them "you", never by name); `office_name` = `campaign_strategy_context.candidate_office` (fallback `official_office_name` — the readable name for web search); `state` / `electionDate` = the context's `state` / `relevant_election_date`. The roster is `campaign_strategy_context.candidates[]`, and it INCLUDES the candidate. (`race_id` is a trace id — ignore it; you never call election-api.)

The one thing you must derive — the rest of the instruction depends on it:

1. **Seed opponents** — find the candidate's own row via `is_user` (match `user_email` to `candidates[].email`, case-insensitive + trimmed; fall back to exact normalized `full_name`). The seed opponents are every OTHER row; each carries `first_name`, `last_name`, `full_name`, `party`, `is_incumbent`, `website_url`, `email` — treat their facts as "GoodParty.org Data", `source: "election-api"`.

`partisanType` is given to you at `campaign_strategy_context.partisanType` (do not infer it — read it; it may be `null`). It only affects the party line in Step 5.

Write `/workspace/scratch/_race.json` = `{"candidate_name", "office_name", "state", "partisanType"}` (your derived values) so the assembler can read them — it no longer gets them from PARAMS. (`mkdir -p /workspace/scratch` first.)

### Step 1 — Discover late filers via web search and merge

The seed opponents (from Step 0, derived from `campaign_strategy_context.candidates`) are authoritative for known filers but lag reality: late filers, write-ins, and especially independents are often missing. Do discovery in **ONE upfront pass, BEFORE you research anyone** — run AT MOST 2 WebSearch queries, finalize the full opponent list, then never return to discovery. Dispatching researchers, then discovering more, then dispatching again serializes the run and is the #1 cause of slow runs — do not do it.

- `candidates running for <office_name> <state> <electionDate>`
- `<office_name> candidates <election year>` and a ballot-info variant, e.g. `<state> sample ballot <office_name> <year>`

Prefer official sources for the roster: the county / state board of elections, the local clerk's sample ballot, Ballotpedia's race page, recent local news race previews.

**The race MUST line up. A wrong-race candidate is far worse than a missed late filer.** `PARAMS` defines the EXACT race: `office_name` + jurisdiction + `electionDate`. Before adding ANY web-found name, all three must be confirmed:
- **Same office** — must match `office_name`, not just the same city or office *type*. "City Council" ≠ "Government Study Commission" ≠ "Mayor". An office mismatch is the most common error; reject it.
- **Same jurisdiction** (city / district / subarea) and **same `electionDate`**.
- **Found on an authoritative roster** — county/state board of elections, the clerk's sample ballot, or Ballotpedia's race page for THIS office. A stray news mention is not enough.

**Default-drop on ambiguity:** if you cannot positively confirm all three from an authoritative source, DROP the name. Do not add unconfirmed candidates.

**Hard cap:** the final opponent list (seed + confirmed web adds) must not exceed **20**. The seed roster is authoritative — keep ALL seed opponents (a large race can legitimately have 11+ filers; research every one). The cap guards against discovery pollution, not against a genuinely large seed roster: **web search may add AT MOST 3 names beyond the seed**; if you found more web candidates, keep the 3 best-confirmed and stop. If the seed roster ITSELF exceeds 20, research the first 20 in roster order.

**Merge rules:**
- Skip any name that is the candidate you write for (`candidate_name`, derived in Step 0), matching loosely (normalize case, strip middle initials / suffixes / accents).
- Skip any name already among the seed opponents (from Step 0) (same fuzzy match) — the seed row already has richer fields.
- Otherwise, ONLY if it passed the race-match gate above, append a new opponent in the SAME shape as the seed rows: `{first_name, last_name, full_name, party: <if stated, else null>, is_incumbent: null, website_url: null, email: null, source: "web", discoverySource: "<authoritative-roster url confirming this office+jurisdiction+date>"}`.

**Seed candidates are authoritative filers — keep them even when web search finds nothing.** A name in the seed roster is a real filing; web silence does not disconfirm it. Such a candidate stays in the list and routes to the "No public information found" line in Step 5. Web search can only ADD or ENRICH opponents — never remove a seed candidate. The one exception is obvious test/junk data (placeholder names like "Jack Test", `@goodparty.org` / `+tag` emails): drop those.

If BOTH the seed roster and web search find no opponent other than the candidate, the race is uncontested as far as you can tell — handle it in Step 5.

### Step 2 — Opponent set (no cross-primary)

This experiment runs only on **general elections**, so there are no party-specific primaries: every non-self opponent (seed + confirmed web adds from Step 1) is a real opponent — research all of them in Step 3. There is no cross-primary set and no party-based filtering.

(If primary support is added later, `partisanType` / `isPrimary` would arrive as inputs and re-introduce cross-primary tagging here.)

### Step 3 — Research each opponent (the fan-out unit)

Per-opponent web research is the slow part, and opponents are independent. **Treat each opponent as one independent research unit.** The harness gives you a `researcher` subagent and lets you dispatch several concurrently via the `Agent` tool — dispatch up to 20 at once (one research unit per opponent; dispatch ALL opponents in a single turn per Step 3's dispatch rule), then collect.

**Write the shared researcher brief ONCE, then dispatch SHORT pointers — do NOT re-author a full prompt per opponent (that is the single biggest wall-clock waste).** Write the entire per-unit brief below (the bullets in this step, verbatim, with `<OPPONENT>`/`<SEED>` as placeholders) ONE time to `/workspace/scratch/researcher_brief.md`. Then dispatch each researcher with a TINY `Agent` prompt — only the per-opponent slot, not the rules:

```
Read /workspace/scratch/researcher_brief.md — that is your full brief, follow it exactly.
Your assigned opponent: <full name>. Seed data: <the opponent's seed JSON>. Your index: NN.
Write your result to /workspace/scratch/opp_NN.json and return only the line "opp_NN written".
```

Emit ALL N of these short `Agent` calls in a SINGLE assistant turn, back to back, with no reasoning between them. Authoring N short pointers costs a fraction of authoring N full prompts, and the brief file means every researcher still gets the complete rules. The researcher's own base prompt already tells it to verify URLs with `pmf_runtime.http.head` — the brief adds the opposition-research specifics (output contract, format).

**Each research unit (whether dispatched as a subagent or run inline) does exactly this, self-contained:**

- **Identity + context:** the opponent's full name, plus `office_name` (the readable one, NOT a BallotReady normalization), `state`, election date.
- **Seed data for this opponent:** `party`, `is_incumbent`, `website_url`, `email`, `source`. Facts already in the seed (party, incumbency) are citeable as "GoodParty.org Data".
- **Job (keep it tight — this is per-opponent and runs N-way, so wasted calls multiply):** run **AT MOST 2 `WebSearch` queries** for this one person (`"<full name>" <office_name> <state>` and a `campaign`/`candidate` variant). **If the discovery pass (Step 1) already surfaced this person with concrete facts (e.g. vote count, incumbency, role) in its snippets, pass those facts into the research unit and have it run just ONE confirming `WebSearch`** — a second query on someone already well-characterized is wasted time on the critical path, since the slowest research unit gates the whole fan-out. Reserve the second query for thinly-sourced opponents. **Pull the 2-3 sentence profile and 2-3 facts from the SEARCH-RESULT SNIPPETS themselves — do NOT fetch or render pages just to extract facts.** Only escalate to fetching a page body (`http.get`, browser, last resort) if a specific claim genuinely cannot be confirmed from snippets. Capture the campaign/social/news URLs worth citing from the results.
- **The research unit must NEVER name the candidate you write for (`candidate_name`, from Step 0).** Each unit describes ONLY its one opponent. If a search snippet mentions the candidate alongside the opponent, do not carry that name into the `summary` or `facts`. Naming the candidate forces a costly clean-up round-trip during assembly — prevent it at the source by telling each research unit, in its prompt, that the candidate's name must not appear in its output at all.
- **Source rules (enforce):**
  - Prefer: official government pages (city/county/state), major news outlets (AP, Reuters, local NPR, regional papers of record), the candidate's own campaign site, Wikipedia only as a secondary source.
  - Avoid / never cite: aggregator sites with stale data; opinion blogs with no named author; LLM-generated summary pages and auto-generated fact-check/aggregator stubs (they return 200 but are machine-generated); PR-wire and self-published press-release sites (`pr.com`, PRNewswire, EIN Presswire — paid placements, not reporting). If a platform claim only appears on a PR wire, attribute it as "according to the candidate's own announcements" rather than citing the wire as fact.
  - Ground every fact in a real result. Do not infer or invent. If nothing is findable beyond the name, return `no_info: true`.
- **Verify URLs inside the research unit with `pmf_runtime.http.head(url)`** (the cheap, non-browser check — see the escalation ladder in CRITICAL RULES): drop any URL whose `r["status"] != 200`; if it redirected, cite `r["final_url"]`. Only if `head` returns 403/405 on a site you believe is real should you escalate to `http.get(url)` (browser). **NEVER verify with `curl`, `wget`, `requests`, `httpx`, or `urllib`** — the container has no egress and each HANGS ~30s+ before failing, multiplied across every URL in every unit. `pmf_runtime.http.head` is the ONLY verification call. LinkedIn URLs almost never verify for non-authenticated bots — drop them. The URLs you return are now considered verified; the parent will NOT re-verify them.
- **When you author each subagent's prompt, COPY the verification rule into it verbatim:** "Verify URLs with `pmf_runtime.http.head(url)` only. Never use curl/wget/requests/urllib — they hang in this container." A subagent that improvises `curl` is the #1 cause of a research unit running for minutes instead of seconds.
- **If you cannot confirm an opponent in your 1-2 searches, return `no_info: true` immediately — do NOT keep searching or escalate to browser/curl to chase a name that may not exist.** A mismatched or low-coverage name (e.g. a seed name not found on the ballot) must bail fast; a research unit that flails on an unconfirmable name gates the entire fan-out.
- **Each research unit also formats its OWN markdown block.** This is the single biggest assembly speedup: per-opponent formatting is the slow serial step when the parent does it for all N at the end, so push it into the parallel units. The unit returns a `markdown_block` string — the fully-formatted, final bullet for THIS opponent, following the exact template in Step 5, with every global rule already applied (refer to the campaign owner as "you" and NEVER name `candidate_name` (from Step 0); no em dashes; the party line follows Step 5 (`partisanType` case-insensitively `nonpartisan` → `Nonpartisan (race is nonpartisan)`, else the opponent's `party` or "Unknown"); only 200-verified URLs; if `no_info`, the block is the single "No public information found as of <today's date>." line under the opponent's name). The parent will concatenate these blocks verbatim — it will NOT re-format, re-summarize, or re-verify them, so the block must be publish-ready.
- **Return contract (exactly this shape per opponent):**
  ```json
  {
    "full_name": "Jane Doe",
    "incumbent": "Yes | No | Unknown",
    "summary": "2-3 sentence profile, grounded in verified sources",
    "facts": [
      {"text": "fact in 1-2 sentences", "source_label": "LAist", "url": "https://...verified-200..."}
    ],
    "websites": ["https://...verified-200 campaign or social URL..."],
    "no_info": false,
    "markdown_block": "- Jane Doe\n  - Party affiliation: ...\n  - Incumbent: ...\n  - Political summary: ...\n    - fact ([source](url))\n  - Websites found:\n    - https://..."
  }
  ```
  An opponent with nothing found returns `{"full_name": "...", "incumbent": "Unknown", "summary": null, "facts": [], "websites": [], "no_info": true, "markdown_block": "- <full name>\n  - No public information found as of <today's date>. You should conduct local research."}`. Map the seed `is_incumbent`: `true` -> "Yes", `false` -> "No", `null` -> "Unknown".
- **The brief (`researcher_brief.md`) must include the exact Step 5 per-opponent template and the global format rules**, and require `markdown_block` in the written fragment. A block that is already publish-ready is what lets assembly be a pure concatenation.
- **Each research unit WRITES ITS RESULT TO A FILE instead of returning it inline.** Before dispatching, `mkdir -p /workspace/scratch` and assign each opponent a zero-padded index NN in original opponent order (01, 02, 03, ...). Each unit writes its complete return-contract JSON object (all fields incl. `markdown_block`) to `/workspace/scratch/opp_<NN>.json` and returns ONLY the line `opp_<NN> written` — NOT the JSON. This keeps the parent's context lean (it never re-reads N full blobs) and lets assembly be a single deterministic merge over the files.

After all units return, the fragments are on disk at `/workspace/scratch/opp_*.json`, one per opponent. You will merge them in Step 5 with ONE script — do not read them turn-by-turn.

**Sequential fallback:** if no subagent dispatch is available, run the exact same per-opponent brief sequentially — loop over the opponents, doing one's `WebSearch` + `pmf_runtime.http` URL verification before the next, producing the same return-contract JSON per opponent. The output is identical; only the wall-clock time differs.

### Step 4 — Final verification audit

**TRUST the research units — do NOT re-verify what they already checked.** Each unit verified its own URLs with `http.head` and returned only 200 URLs. The default audit is a pure **in-memory** dedupe/sanity pass: collect every cited URL into a set, drop exact duplicates, confirm each came from a unit that returned it as 200. Do NOT loop a network check over all cited URLs as a matter of course — that adds a full round-trip batch on the critical path for URLs already known-200.

**Verify each unique URL AT MOST ONCE.** Within a research unit and across the whole run, never run `http.head` twice on the same URL — dedupe your URL set first, then check each once. Re-checking the same batch (e.g. verifying an opponent's URLs, then verifying an overlapping set again) is wasted time on the critical path and a common slow-down.

If you DO have a concrete reason to re-check a specific URL (a unit's return looked malformed, or you gathered a new URL yourself during assembly), verify it with **`pmf_runtime.http.head(url)` and NOTHING ELSE.** Verification is ALWAYS `http.head`. **NEVER use `curl`, `wget`, `requests`, `httpx`, or `urllib` to check a URL** — the container has no egress, so each of those HANGS ~30s+ before failing and torches the time budget. If you catch yourself typing `curl` in a Bash command to check a status code, STOP and use `pmf_runtime.http.head` instead. Never `http.get` (browser) here. Drop any URL that is not 200 before assembling Step 5. The published section contains only 200-verified URLs.

### Step 5 — Assemble the output

**Assembly is ONE command — do NOT write a merge script, regenerate, re-summarize, re-verify, or hand-compose.** A ready-made merge script `/workspace/assemble.py` is provided for you. The research units already wrote publish-ready fragments to `/workspace/scratch/opp_*.json`. To assemble:

1. Run **`python3 /workspace/assemble.py`** once. It reads the fragments + `/workspace/scratch/_race.json` (the derived race fields from Step 0 — `candidate_name`, `office_name`, `state`), concatenates each fragment's `markdown_block` under the `### Opposition Research` header, builds `opponents` (without `markdown_block`), sets `race.{office_name,state,opponent_count}` and `generated_at`, writes `/workspace/output/opposition_research.json`, and runs the STRUCTURAL/FORMAT spot-checks (candidate name absent, no em dash, opponent_count matches) — printing a PASS/FAIL block and exiting non-zero on FAIL. `assemble.py` does NOT do the URL-quality checks — you still perform those from the `## Spot-check` section below (a cited URL actually loads and mentions the opponent; every fact URL returned 200 in Step 4).
2. Run **`python3 /workspace/validate_output.py`** once.

Do NOT run WebSearch, `http.head`, or `http.get` here, and do NOT read the fragments turn-by-turn. If `assemble.py` reports a FAILED spot-check, open the offending `/workspace/scratch/opp_<NN>.json` fragment, fix its text in place (no network, no regeneration), and re-run `assemble.py`.

For the uncontested case (zero fragments — both the seed roster and web search found only the candidate), `assemble.py` emits the standard uncontested line automatically.

```markdown
### Opposition Research

- [Opponent full name]
  - Party affiliation: [see rule below]
  - Incumbent: [Yes / No / Unknown]
  - Political summary: [2-3 sentence summary, grounded in search results]
    - [Key position or background fact 1] ([source](url))
    - [Key position or background fact 2] ([source](url))
    - [Key position or background fact 3, if available] ([source](url))
  - Websites found:
    - [URL 1, e.g. campaign website]
    - [URL 2, e.g. Facebook account]
    - [URL 3, e.g. Instagram account]
```

**Party affiliation line:** if `partisanType` is `nonpartisan` (match case-insensitively, trimmed — election-api may send `"Nonpartisan"`), write `Nonpartisan (race is nonpartisan)` (the party labels are registration noise, not the contest). Otherwise write the opponent's `party` value (e.g. "Democratic", "Republican"), or `Unknown` if it is null.

**Websites found line:** include only campaign and social URLs (campaign site, Facebook, Instagram, X, official campaign LinkedIn). Drop URLs from `urls[]` that are not campaign assets — an employer or government-office page is not an opposition website. Use the verified URL from Step 4; if it redirected, cite `r["final_url"]` (the `http.head` redirect key — `source_url` only exists on `http.get`/browser results). If an opponent has no verifiable campaign or social site, write exactly one bullet: `No campaign or social websites found as of <today's date>.`

If no opponent information is found for a given candidate (`no_info: true`), write: `No public information found as of <today's date>. You should conduct local research.`

**Empty-field handling — evaluate in this order:**
1. **Race uncontested** (merged list has zero opponents — both seed roster and web search found only the candidate): write `No opponents are currently registered for this race as of <today's date>. Continue to monitor, since filing windows may still be open.`
2. **Otherwise**: render each opponent in the standard format above.

Then build the JSON artifact:
- `markdown` — the header + concatenated `markdown_block`s (in order). Built by joining, not regenerating.
- `opponents` — the collected per-opponent return-contract objects (`full_name`, `incumbent`, `summary`, `facts`, `websites`, `no_info`), in order. Drop the `markdown_block` field from each object here (it lives in the assembled `markdown`, not duplicated per opponent).
- `race` — `{office_name, state, opponent_count}` where `opponent_count` is the number of researched opponents.
- `generated_at` — current ISO 8601 timestamp.

Write it to `/workspace/output/opposition_research.json`.

### Step 6 — Validate

```bash
python3 /workspace/validate_output.py
```

## Constraints (must follow)
- Plain, direct U.S. English. No em dashes. No jargon.
- Bullet points are 1-3 sentences each — not fragments, not essays.
- Grounded in what web search actually returned. Do not fabricate names, affiliations, or URLs.
- Produce ONLY the markdown section in `markdown`. No title page, no intro, no summary after.
- Replace the candidate's name with "you" throughout.
- Numbers, not words: "50% + 1", not "half"; "5x projected turnout", not "five times".
- Be mindful of local election rules: North Dakota has no voter registration; Connecticut has no counties.
- Every cited URL must have returned HTTP 200 in Step 4.

## Spot-check
Validator-passing JSON can still be garbage. Run the spot-check as ONE script that loads the artifact a single time and prints every check at once — do NOT issue a separate `python3 -c` per check (each is a turn with inference between it, and the round-trips dominate the assembly phase). Load once, assert all of the following, print a single PASS/FAIL block, then fix and re-run only if something failed:
- **A cited URL doesn't load or doesn't mention the opponent** — don't trust search snippets blindly. If you fetched the body with `pmf_runtime.http.get` during Step 3 (the last-resort case, when snippets were insufficient), confirm the body actually references the person and the claim. If you did NOT fetch the body (the common case — facts came from search snippets), confirm the snippet text you used is reflected in `facts[].text` with a matching source. Do NOT call `http.get` here — Steps 4 and 5 forbid network calls at assembly time.
- **Every fact's URL returned 200** in Step 4. If any didn't, the citation must be gone from `markdown` AND from the opponent's `facts`/`websites`.
- **`opponent_count` equals the number of opponents you rendered** in `markdown` (excludes you).
- **The candidate's own name never appears** in `markdown`; it always reads "you".
- **A seed opponent who returned `no_info` still appears** in `markdown` with the "No public information found" line — web silence does not delete a real filer.

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|
| `r.status_code` raises `AttributeError` | `pmf_runtime.http.get` returns a plain dict | Use `r["status"]`, not `.status_code` |
| `WebFetch` returns "Unable to verify if domain X is safe" | Quarantined network can't reach claude.ai's safety check | Discover with `WebSearch`, verify with `pmf_runtime.http.head`; escalate to `pmf_runtime.http.get` (browser) only if `head` returns 403/405 |
| LinkedIn URL returns 999 or 404 | LinkedIn hard-blocks non-authenticated bots | Drop the citation; never cite a LinkedIn URL |
| A web-surfaced "candidate" isn't really in this race | Wrong district, past cycle, or withdrew | Confirm via an official roster before adding; if you can't confirm they're on THIS ballot for THIS election, drop them |
| A seed opponent looks like test/junk data | Non-production rows leaked into the roster | Drop obvious test rows; do not publish them |
| `No artifact files found in /workspace/output` | Ran out of turns or never wrote the file | Write `/workspace/output/opposition_research.json` early and update it; keep research units tight |
