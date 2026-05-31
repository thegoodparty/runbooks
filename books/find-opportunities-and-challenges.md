Produce the Opportunities and Challenges of a candidate's campaign plan — up to 3 opportunities (structural advantages) and up to 3 challenges (structural risks), each a 1-3 sentence bullet grounded in this race's numbers, with every external claim cited and every cited URL returning HTTP 200. Output is a structured JSON artifact, not markdown.

This is the source runbook — the human-runnable version of the workflow. Once stable, port it to a PMF experiment via `books/convert-runbook-to-experiment.md`. Naming: `find-opportunities-and-challenges.md` → `experiments/opportunities_and_challenges/`.

This replaces the Opportunities and Challenges sections of gp-api's `strategic-landscape` pipeline (the Opposition Research section is its own `opposition_research` experiment). The logic here is ported from gp-api `src/campaignStrategy/services/strategicLandscape.prompts.ts` — but collapsed to a single step: the experiment emits the structured JSON directly, with no intermediate markdown-section render or extraction.

**Two ways this runs — the agent never calls election-api:**
- **In the experiment (production):** gp-api injects every field into the dispatch params — the `user_*` identity fields plus `campaign_strategy_context` (the election-api result it fetched once). The agent reads those; it does not know election-api exists.
- **Locally (this runbook):** feed the same shape — an enriched record, or a test set of them — to `scripts/python/campaign_strategy_context.py`, which assembles the context. No live call. Same script the `opposition_research` runbook uses; here you only read its race-level fields.

Both lists are built from the SAME context. Opportunities reframe the numbers as advantages to press; Challenges reframe them as risks to plan around.

## Prerequisites

**books/.env variables**: none.
**scripts/.env variables**: none.
**Tools**: `scripts/python/campaign_strategy_context.py` (assemble the context from an enriched record), `scripts/python/verify_urls.py` (URL vetting), `scripts/python/validate_opportunities_and_challenges.py` (output-schema check — created during the convert step), `uv`, web search.
**Inputs (the injected contract)** — gp-api assembles these from its DB + one election-api call before dispatch; the agent just reads them:
- `race_id` — trace / idempotency identifier only; the agent does not reason over it.
- `user_email`, `user_first_name`, `user_last_name`, `user_full_name`, `user_party_affiliation`, `other_party` — the candidate identity (party resolves `Other` → `other_party`; bullets address them as "you", never by name).
- `campaign_strategy_context` — the race-level numbers + roster (the raw election-api result). This is the only source besides light web search.

**Output**: a JSON artifact `{ "opportunities": [...], "challenges": [...] }` — 1-3 strings each, where every string is one finished bullet with its citation inlined as `... ([source](url))`. There is no markdown render step; the JSON is the canonical and only output.

## What you need to know about the data

The opportunities and the challenges are DERIVED from `campaign_strategy_context`, not researched from scratch. The fields that drive them:

- `win_number_estimate` / `projected_turnout` — a low win number is an opportunity; a high one relative to the candidate's resources is a challenge.
- `number_of_seats` vs `candidate_count` (and the roster in `candidates[]`) — few opponents for the seats available is an opportunity; a crowded field that splits the vote is a challenge.
- incumbency — no candidate with `is_incumbent: true` means an open seat (opportunity); a `true` incumbent with party backing is a challenge.
- `general_election_date` / `primary_election_date` vs `today` — a long runway is an opportunity; an election very soon is a challenge.
- `partisan_type` / `user_party_affiliation` — `nonpartisan` means party labels are registration noise, not the contest. In a partisan race, watch for opponents in a different party's primary (not yet a contestant until the general).
- `contacts_needed_estimate` — the voter-contact goal (5× the win number); frames how reachable the win number is.

Treat `not available` / null fields as unknown — do not invent values, and do not build a bullet on a number you do not have.

## Steps

### 1. Get the assembled context

**In the experiment:** read `campaign_strategy_context` + the `user_*` fields from `PARAMS_JSON`. No election-api call.

**Locally:** assemble it from an enriched record (or a test set):

```bash
cd scripts/python
uv run python campaign_strategy_context.py --record sample_race.json > context.json
# or a whole test set (array of records):
uv run python campaign_strategy_context.py --records users-enriched.json > contexts.json
```

Read off the numbers you will reason over:

```bash
jq '{candidate_office, official_office_name, office_type, office_level, state,
     user_party_affiliation, partisan_type, number_of_seats, candidate_count,
     general_election_date, primary_election_date, projected_turnout,
     win_number_estimate, contacts_needed_estimate}' context.json
jq '[.candidates[] | {full_name, party, is_incumbent, is_user}]' context.json
```

### 2. Derive the signals (numbers first, web second)

Most bullets come straight from the numbers above and cite `GoodParty.org Data`. Identify, for THIS race:

- **Opportunity signals** — a low `win_number_estimate`; an open seat (no `is_incumbent: true` in the roster); `candidate_count` small relative to `number_of_seats`; a long runway to `general_election_date`; a reachable `contacts_needed_estimate`.
- **Challenge signals** — a crowded field (vote-splitting); an incumbent (`is_incumbent: true`), especially with party backing in a partisan race; an election very soon (short outreach window); a high win number relative to a first-time/independent campaign's resources.

Use **web search only** to corroborate an external fact you want to cite (e.g. an incumbent's fundraising, a recent local result, a redistricting change). The structural bullets do not need the web; the numbers carry them.

### 3. Write the bullets

Up to **3 opportunities** and up to **3 challenges**. Each bullet is one string in the output arrays:
- 1-3 sentences, specific to THIS race and THESE numbers — not generic campaign advice.
- Every claim has a compact, Wikipedia-style citation inlined as `... ([source](url))`; claims from the context cite `GoodParty.org Data`, external claims cite the source URL.
- Follow the constraints below (no em dashes, "you" not the name, numbers not words, local election rules).

### 4. Verify every cited URL

```bash
cd scripts/python
uv run python verify_urls.py < cited_urls.txt > url_status.json
jq '[.[] | select(.ok == false)]' url_status.json   # must be empty
```

Drop any citation whose URL is not 200 before assembling. The published bullets contain only 200-verified URLs.

### 5. Assemble and validate the output

Build the JSON artifact `{ "opportunities": [<1-3 strings>], "challenges": [<1-3 strings>] }`, each string a finished bullet with its citation inlined. Then validate:

```bash
cd scripts/python
uv run python validate_opportunities_and_challenges.py /path/to/opportunities_and_challenges.json
```

Each array must have at least 1 and at most 3 entries. If a list genuinely has nothing race-specific to say (rare — every race has a win number and a date), still emit at least one bullet grounded in the strongest number you do have.

## Constraints (must follow)

Ported from the gp-api prompt's COMMON_CONSTRAINTS, scoped to the bullet strings (there is no markdown section to format):

- Write in plain, direct U.S. English. No em dashes. No jargon.
- Each bullet is 1-3 sentences — not a fragment, not an essay. No section headers, list markers, or preamble inside a string; it is just the bullet's prose plus its inline citation.
- Always prefer the glossary's language; do not invent synonyms for it.
- Do NOT refer to the candidate by name — replace the name with "you".
- Prefer numbers over words: "50% + 1", not "half"; "5 times the projected voter turnout", not "five times".
- Prioritize local election rules over jargon (e.g. North Dakota has no voter registration; Connecticut has no counties; California uses a top-two primary; Louisiana uses a jungle primary).
- Every cited URL must return HTTP 200 (Step 4).
- Every opportunity and challenge must be specific to this race and these numbers, not generic advice.

## Output schema

The artifact validates against `scripts/python/opportunities_and_challenges.schema.json` (created in the convert step). Shape:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["opportunities", "challenges"],
  "properties": {
    "opportunities": { "type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 3 },
    "challenges":    { "type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 3 }
  }
}
```

`minItems: 1` mirrors gp-api's `OpportunitiesSchema` / `ChallengesSchema` — an empty list is treated as a failed generation, not a valid result.

## Glossary (preferred language — ported from the gp-api prompt)

- **registered voters**: total pool of voters eligible to cast a ballot for a race, from the latest voter file.
- **projected voter turnout**: estimated registered voters expected to cast a ballot in this specific election. Historically +/- 1.5% of actual.
- **projected votes needed to win**: 50% + 1 of projected voter turnout.
- **targeted voter contact goal**: total contacts the campaign aims to deliver. Rule of thumb: 5× projected votes needed to win.
- **voter contact**: a contact attempt that reaches an intended voter via a channel capable of conveying the message.
- **likely votes**: estimated votes on track to receive based on contacts to date. 1 likely vote per 5 voter contacts.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| A bullet is generic campaign advice | Not tied to a number in the context | Anchor every bullet to a specific field (win number, seats, date, roster) |
| A bullet cites a number that is `not available` | Built on a null/missing field | Drop it; only reason over numbers actually present |
| Opportunity and challenge say the same thing inverted | Thin signal set | Pick distinct structural facts for each list; do not mirror one bullet into the other |
| Party labels treated as the contest in a nonpartisan race | `partisan_type` is `nonpartisan` | Treat party as registration noise; don't frame a bullet around party |
| `verify_urls.py` flags a URL the browser can open | Site blocks bot HEAD/GET | Try the `final_url`, else replace the citation; drop if it can't be verified |
| Empty `opportunities` or `challenges` array | Degenerate generation | Schema requires `minItems: 1`; emit at least one bullet on the strongest available number |
