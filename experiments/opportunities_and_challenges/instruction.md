# Opportunities and Challenges

Produce the Opportunities and Challenges of a candidate's campaign plan: up to 3 structural advantages and up to 3 structural risks, each a finished 1-3 sentence bullet grounded in THIS race's numbers, with every external claim cited and every cited URL verified HTTP 200. Both lists are derived from the `campaign_strategy_context` handed to you in params (gp-api hydrated it from election-api before dispatch); the numbers carry most bullets, and light web search corroborates any external fact you cite. Output is structured JSON — there is no markdown section to render.

## BEFORE YOU START
1. Read this entire instruction end-to-end before executing anything.
2. Maintain a TodoWrite list mirroring the TODO CHECKLIST below.
3. Your params are in the `PARAMS_JSON` env var. Read them once at the top.
4. Write the final artifact to `/workspace/output/opportunities_and_challenges.json` and nowhere else.
5. Run `python3 /workspace/validate_output.py` before declaring success.
6. Perform the spot-check at the bottom — validator-passing data can still be garbage.

## TODO CHECKLIST
1. Read params; identify the candidate (`is_user`) and read the race numbers + roster (Step 0).
2. Derive the opportunity signals and the challenge signals from the numbers (Step 1).
3. Corroborate any external claim with WebSearch and verify its URL with `http.head` (Step 2).
4. Write up to 3 opportunities and up to 3 challenges, each a bullet string with its citation inlined (Step 3).
5. Write the artifact JSON (Step 4).
6. Validate, then spot-check (Step 5).

## CRITICAL RULES

**Network egress is quarantined.** The ONLY ways to reach the internet are `WebSearch` and the broker-proxied `pmf_runtime.http` helpers. `urllib`/`requests`/`httpx`/`curl`/`wget`/`socket` do NOT work — they hang ~30s+ then fail, torching the time budget. NEVER write code or shell that fetches a URL directly.

**Web-access ladder — use the cheapest rung; do NOT jump to the browser:**
1. `WebSearch` (free, fast) — discovery. Snippets usually answer the question; only fetch a page when you must confirm a claim against its body.
2. To VERIFY a URL is live before citing it, run exactly this in Bash:
   ```bash
   python3 -c "from pmf_runtime import http; print(http.head('<url>'))"
   ```
   It returns `{"status": int, "final_url": str}`. Cite a URL only if `status == 200`; on a redirect, cite the `final_url` unless the redirect only added tracking params.
3. `pmf_runtime.http.get(url)` (browser render) is a LAST RESORT — only when `head` returns 403/405 on a real site or you must read the page body.

**Opponent data is provisional — do NOT build bullets on it.** The roster in `campaign_strategy_context` (`candidate_count`, `candidates[]`, and each candidate's `is_incumbent`) is currently incomplete and lags reality; who is actually running is owned by a separate opposition-research process, not this one. Do NOT base any opportunity or challenge on the number of opponents, whether it is an open seat, or whether anyone is an incumbent, as read from this roster. Build every bullet from the reliable race numbers (`win_number_estimate`, `projected_turnout`, `contacts_needed_estimate`, `registered_voters`, election dates, `number_of_seats`, `office_level`/`office_type`, `state`, `partisan_type`) and from web search. If you want to make a point about the field (open seat, crowded race, a strong incumbent), confirm it with a web search and cite that source — never assert it from the provided roster.

**Bullet-content rules (every opportunity and challenge string):**
- Plain, direct U.S. English. **No em dashes.** No jargon.
- 1-3 sentences. No section headers, list markers, or preamble inside the string — just the bullet's prose plus its inline citation `... ([source](url))`.
- Refer to the candidate as **"you"**, NEVER by name.
- Numbers, not words: "50% + 1" not "half"; "5 times the projected voter turnout" not "five times".
- Specific to THIS race and THESE numbers — never generic campaign advice.
- Cite every claim. Claims from the provided context cite `GoodParty.org Data`; external claims cite a source URL verified 200.
- Respect local election rules (e.g. North Dakota has no voter registration; Connecticut has no counties; California uses a top-two primary; Louisiana uses a jungle primary).

## Steps

### Step 0 — Read params, identify the candidate, read the numbers

Read `PARAMS_JSON` once. The candidate you write FOR is `user_full_name` (output says "you", never the name). Find the candidate's own row via `is_user`: match `user_email` to `campaign_strategy_context.candidates[].email` (case-insensitive + trimmed), falling back to exact normalized `full_name`. You do not list opponents here, but identifying the candidate keeps their name out of the bullets and lets you read the roster correctly. (`race_id` is a trace id — ignore it; you never call election-api.)

Read the fields the bullets are derived from:

```bash
python3 - <<'EOF'
import json, os
p = json.loads(os.environ["PARAMS_JSON"])
c = p["campaign_strategy_context"]
print("office:", c.get("candidate_office") or c.get("official_office_name"))
print("state:", c.get("state"), "| partisan_type:", c.get("partisan_type"))
print("party (you):", p.get("user_party_affiliation"), "| other_party:", p.get("other_party"))
print("seats:", c.get("number_of_seats"), "| candidate_count:", c.get("candidate_count"))
print("win_number_estimate:", c.get("win_number_estimate"), "| projected_turnout:", c.get("projected_turnout"))
print("contacts_needed_estimate:", c.get("contacts_needed_estimate"))
print("general:", c.get("general_election_date"), "| primary:", c.get("primary_election_date"))
for cand in c.get("candidates", []):
    print("  -", cand.get("full_name"), "| party=", cand.get("party"), "| incumbent=", cand.get("is_incumbent"))
EOF
```

Treat any null / missing field as unknown. Do NOT invent a value and do NOT build a bullet on a number you do not have.

### Step 1 — Derive the signals (reliable race numbers first)

Most bullets come straight from the reliable numbers below and cite `GoodParty.org Data`. For THIS race, identify:

- **Opportunity signals** — a low `win_number_estimate` relative to `projected_turnout` (how small a share of the vote wins); a `contacts_needed_estimate` that is achievable against the available `registered_voters` / `unique_cellphones`; a long runway from today to `general_election_date` / `primary_election_date`; favorable office structure (`number_of_seats`).
- **Challenge signals** — a high win number relative to a first-time or independent campaign's resources; a large `contacts_needed_estimate` against the `registered_voters` you must mobilize; an election very soon (short outreach window from today to the relevant date).

Do NOT derive a bullet from the opponent roster (`candidate_count`, `candidates[]`, `is_incumbent`) — see the opponent-data warning in CRITICAL RULES. If a point about the field (open seat, crowded race, a strong incumbent) is genuinely central, confirm it with a web search in Step 2 and cite that source; never assert it from the provided roster.

If `partisan_type` is `nonpartisan`, party labels are voter-registration noise, not the contest — do not frame a bullet around party.

### Step 2 — Corroborate external claims (web)

The structural bullets do not need the web; the numbers carry them. Use `WebSearch` ONLY to corroborate an external fact you choose to cite (e.g. an incumbent's fundraising, a recent comparable local result, a redistricting change). Verify every external URL with `http.head` (CRITICAL RULES) and drop any that is not 200.

### Step 3 — Write the bullets

Write up to **3 opportunities** and up to **3 challenges** (at least 1 each). Each is one string in the output arrays: a finished 1-3 sentence bullet with its citation inlined. Make the two lists distinct — do not mirror one bullet inverted into the other. Follow every bullet-content rule in CRITICAL RULES.

### Step 4 — Write the artifact

Write `/workspace/output/opportunities_and_challenges.json` exactly as:

```json
{ "opportunities": ["<bullet> ([GoodParty.org Data])", "..."], "challenges": ["<bullet> ([source](https://...))", "..."] }
```

Each array has 1-3 entries. Nothing else in the file.

### Step 5 — Validate

```bash
python3 /workspace/validate_output.py
```

Fix any schema error before declaring success.

## Spot-check
- Each array has 1-3 entries; neither is empty.
- Every bullet is tied to a specific number from the context, not generic advice.
- The candidate's name does NOT appear in any bullet (you replaced it with "you").
- No em dash (U+2014) appears anywhere in the output.
- Opportunities and challenges are distinct, not the same fact stated twice.
- No bullet relies on the opponent roster — no claim about opponent count, open-seat status, or incumbency comes from `candidate_count` / `candidates[]` / `is_incumbent` (only from a web-confirmed source).
- If `partisan_type` is `nonpartisan`, no bullet treats party as the contest.
- Every external (non-`GoodParty.org Data`) citation URL returned 200.

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|
| A bullet is generic campaign advice | Not tied to a number in the context | Anchor every bullet to a specific field (win number, seats, date, roster) |
| A bullet cites a `not available` number | Built on a null/missing field | Drop it; only reason over numbers actually present |
| Opportunity and challenge mirror each other | Thin signal set | Pick distinct structural facts for each list |
| Bullet claims open seat / N opponents / incumbent | Read it from the provisional roster | Drop it, or web-confirm and cite that source — the roster is not authoritative for the field |
| Run hangs ~30s on a URL | Used `urllib`/`curl`/`requests` | Use `pmf_runtime.http.head` only; never direct egress |
| `validate_output.py` fails on empty array | A list came back empty | Each array needs at least 1 bullet — emit one on the strongest available number |
| Party framed as the contest | `partisan_type` is `nonpartisan` | Treat party as registration noise; reframe the bullet on a structural number |
