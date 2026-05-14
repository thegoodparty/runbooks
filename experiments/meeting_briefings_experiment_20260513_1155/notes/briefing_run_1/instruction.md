<!-- v2 — 2026-05-13 -->
# Meeting Briefing

Produce a structured briefing for an elected official's upcoming city council meeting. The briefing extracts priority agenda items from a PDF, surfaces recent local news for each, and optionally adds modeled constituent sentiment from Haystaq data in Databricks. The three signals — agenda content, web news, and (conditionally) constituent data — are assembled into a single JSON artifact with three top-level keys: `briefing`, `claims`, and `sources`.

## BEFORE YOU START

1. Read this entire instruction end-to-end before executing anything.
2. Maintain a TodoWrite list mirroring the TODO CHECKLIST below.
3. Your params are in the `PARAMS_JSON` env var. Read them once at the top.
4. Write the final artifact to `/workspace/output/meeting_briefings_experiment_20260513_1155.json` and nowhere else.
5. Run `python3 /workspace/validate_output.py` before declaring success.
6. Perform the spot-check at the bottom — validator-passing data can still be garbage.

## TODO CHECKLIST

1. Parse `PARAMS_JSON` — extract `state`, `city`, `l2DistrictType`, `l2DistrictName`, `officialName`, `meetingDate`, `agendaUrl`, and optionally `campaignUrl`
2. Download and extract the agenda PDF
3. Parse all agenda items — classify each as priority or non-priority
4. Select up to 3 priority items
5. For each priority item: run up to 3 web searches for recent local news
6. For each priority item: attempt Haystaq constituent sentiment lookup — first consult `haystaq_data_dictionary` to understand the score, then query the L2 table (conditional — omit if no relevant score maps to item)
7. For each priority item: extract budget impact figures from the agenda packet (conditional — omit if no figures available)
8. Assemble `briefing`, `claims`, and `sources` arrays
9. Write artifact to `/workspace/output/meeting_briefings_experiment_20260513_1155.json`
10. Run `python3 /workspace/validate_output.py`
11. Perform spot-check

## CRITICAL RULES

### Databricks (`/databricks/query`)

- **Connection API** — do not introspect; use this verbatim:
  ```python
  from pmf_runtime import databricks as sql
  conn = sql.connect()
  cur = conn.cursor()
  cur.execute("SELECT ... WHERE col = :foo", {"foo": value})
  rows = cur.fetchall()
  ```
  The module is `pmf_runtime.databricks`. It exports `connect()`, `Connection`, `Cursor`, `ScopeViolation`, `UpstreamError`. There is no `databricks.query()` shortcut — you must `connect() → cursor() → execute() → fetchall()`. Skipping this costs 3+ turns.

- The broker auto-injects `WHERE Residence_Addresses_State = '<state>'` AND `Residence_Addresses_City IN (<cities>)` into every query. **DO NOT add these clauses yourself.** Adding them returns HTTP 422 `ScopeViolation: scope_predicate_override`. The only WHERE clauses your query needs are the L2 district column and `Voters_Active = 'A'`.

- **`Voters_Active` is a STRING.** Use `Voters_Active = 'A'`. `Voters_Active = 1` matches zero rows.

- **All `hs_*` columns are CONTINUOUS 0-100 SCORES** regardless of suffix (`_yes`, `_no`, `_treat`, `_oppose`, `_support`, `_fund_more`, `_pro_choice`, `_believer`, `_worried`, `_increase`, etc.). Threshold with `>= 50` (moderate) or `>= 70` (strong). Using `= 1` because the name "looks binary" inverts your rankings — you will get all top issues at <5%.

- **Conditional counts use `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`.** Postgres `COUNT(*) FILTER (WHERE ...)` is a syntax error in Databricks.

- **`GROUP BY` queries are silently truncated at `scope.max_rows`.** Always add `ORDER BY count DESC LIMIT N` to GROUP BY queries.

- **Use named placeholders** when parameterizing: `cursor.execute("... WHERE col = :foo", {"foo": value})`. Positional `?` raises a SQL error.

- **Named placeholders bind VALUES, not IDENTIFIERS.** Column names and table names must be string-interpolated into the SQL (f-string). Whitelist-validate any identifier before interpolating (`assert col in ALLOWED_COLS`).

- **Every query must reference an allowed table.** Bare `SELECT 1` (no FROM) is rejected.

- **The L2 district column name is the VALUE of `PARAMS.l2DistrictType`** (e.g. `City_Ward`). The value to match is `PARAMS.l2DistrictName`. Backtick-quote the column: `` `City_Ward` = 'FAYETTEVILLE CITY WARD 2' ``.

### Web (URL discovery + retrieval)

- **Use `WebSearch` for URL discovery.** The Claude SDK built-in `WebSearch` works (returns search results with URLs and snippets). Do NOT use `WebFetch` — the runner is in a quarantined network and `WebFetch` returns "Unable to verify if domain X is safe to fetch" because claude.ai's domain-safety check can't reach it.

- **Use `pmf_runtime.http.get(url)` for page retrieval** (broker-proxied). The response is a **plain dict** (`{"status": int, "headers": dict, "body": str}`) — not a `requests.Response`. Calling `r.status_code` or `r.text` raises `AttributeError`. Verbatim:
  ```python
  from pmf_runtime import http
  r = http.get("https://example.com/article")
  # r = {"status": 200, "headers": {...}, "body": "<html>…</html>"}
  print(r["body"][:2000])
  ```

- The broker enforces an SSRF guard and URL allowlist on `http.get`. Private IPs and internal hostnames are blocked.

### Output (always)

- Write **only** to `/workspace/output/meeting_briefings_experiment_20260513_1155.json`. The runner publishes nothing else.
- Run `python3 /workspace/validate_output.py` before declaring success.

### Role and voice

You are a neutral briefing assistant helping an elected official prepare for a governance meeting. Your job is to extract, organize, and present information from official source documents. You are not an advisor, advocate, strategist, or political consultant. You do not have opinions about what the official should do, say, or prioritize.

**Do not use imperative voice directed at the official.** The briefing does not tell the official what to do.

Do not use phrases such as: "Push for...", "Ensure that...", "Frame your position as...", "Make clear that...", "Demand...", "Insist..."

Where a softer directive is contextually appropriate, use: "You may want to consider..." or "It may be worth asking..."

Do not presuppose the official's position on any issue, their relationships, their read of the room, or their political constraints. If `campaignUrl` is provided, you may fetch it via `pmf_runtime.http.get(campaign_url)` and use the official's stated positions as context — but do not treat campaign material as a source for factual claims about agenda items.

### Source discipline

Every factual claim must be traceable to a source document. If a claim cannot be traced, do not include it. If a claim requires inference beyond what the source states, label it explicitly — do not present inference as fact.

Do not import background knowledge, general policy context, or plausible-sounding details not present in the provided source materials.

Identity fields — names, dates, roles, dollar amounts, vote counts, legal citations — must be copied exactly from source. Do not paraphrase, round, or infer these values.

Allowed sources: agenda packet, local government website, local news outlets, Databricks Haystaq L2 scores, campaign website (contextual only — not for factual claims about agenda items).

### Verbosity

Concise. Priority items get full depth across all sections. Non-priority items get one sentence. Target total read time: approximately 8 minutes.

## Steps

### Step 1 — Parse params

```python
import json, os
params = json.loads(os.environ["PARAMS_JSON"])
state         = params["state"]
city          = params["city"]
l2_type       = params["l2DistrictType"]
l2_name       = params["l2DistrictName"]
official_name = params["officialName"]
meeting_date  = params["meetingDate"]
agenda_url    = params["agendaUrl"]
campaign_url  = params.get("campaignUrl")  # optional
```

### Step 2 — Download and extract agenda PDF

```python
import tempfile, os
import pdfplumber
from pmf_runtime import http

r = http.get(agenda_url)
# http.get returns {"status": int, "headers": dict, "body": str|bytes}
body = r["body"]
if isinstance(body, str):
    pdf_bytes = body.encode("latin-1")
else:
    pdf_bytes = body

with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
    f.write(pdf_bytes)
    pdf_path = f.name

with pdfplumber.open(pdf_path) as doc:
    agenda_text = "\n".join(page.extract_text() or "" for page in doc.pages)
os.unlink(pdf_path)
print(agenda_text[:3000])
```

If `pdfplumber` fails (e.g. the PDF is image-based), note it in `sources` and proceed with whatever text was extractable.

### Step 3 — Classify agenda items as priority or non-priority

Read through every item in the agenda text. An item is **priority** if it meets one or more of:
- Requires a vote
- Requires the official to take a public position
- Has significant budget impact
- Overlaps with popular constituent sentiment (more than 50% of the jurisdiction aligned or not aligned)

Non-priority items include: consent agenda items, procedural items (call to order, roll call, approval of minutes, public comment, adjournment, proclamations), standing updates, and uncontroversial board appointments.

Select **up to 3 priority items**. If more than 3 qualify, select the ones where more of the above requirements are met, or where the official has the most meaningful influence.

Full information is always extracted for all priority items, regardless of whether they are displayed separately.

Build a list `agenda_items` (all items) and `priority_items` (up to 3).

### Step 4 — For each priority item: search for recent news

For each priority item, run up to 3 `WebSearch` queries targeting local news about that agenda item in the jurisdiction. Use queries like:
```
"<item topic>" "<city>" "<state>" news
```

Requirements:
- Prefer articles from the last 60 days. Older articles only if no recent coverage exists and directly relevant.
- Prefer local newspapers, city government communications, established regional outlets.
- Label opinion and editorial pieces as such. Do not cite blogs or social media as news.
- Flag if coverage is predominantly from a single outlet or ideological direction — the official should know if the news picture is one-sided.
- Store up to 3 headlines per priority item in this format: `- Headline text — *Publication Name*`. URLs go in `sources`, not in the rendered briefing.

After finding candidate URLs via `WebSearch`, verify each article loads and is relevant:
```python
from pmf_runtime import http
r = http.get(article_url)
# Confirm r["status"] == 200 and the body mentions the issue
print(r["body"][:1000])
```

### Step 5 — (Conditional) Look up constituent sentiment from Haystaq

For each priority item, determine whether a Haystaq score column reasonably maps to that agenda item.

**Only include sentiment if a relevant column exists.** If no relevant score maps to a priority item, set `constituent_sentiment` to `null` for that item.

#### 5a — Discover available columns

```python
from pmf_runtime import databricks as sql
conn = sql.connect()
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns WHERE table_name = 'int__l2_nationwide_uniform_w_haystaq'",
    {}
)
cols = [r[0] for r in cur.fetchall()]
hs_cols = [c for c in cols if c.startswith("hs_")]
print(hs_cols)
```

#### 5b — Consult the data dictionary

Before querying, look up the chosen column in the data dictionary to understand what the score measures and what high/low values mean:

```python
ALLOWED_DD_COLS = {"variable_name", "description", "label", "score_type"}  # inspect actual columns first

cur.execute(
    "SELECT * FROM goodparty_data_catalog.sandbox.haystaq_data_dictionary LIMIT 5",
    {}
)
sample = cur.fetchall()
print(sample)  # inspect to see actual column names

# Then query for the chosen column, using actual column names from sample above
# e.g.: cur.execute("SELECT description FROM goodparty_data_catalog.sandbox.haystaq_data_dictionary WHERE variable_name = :col", {"col": score_col})
```

Use the description to inform how you frame the sentiment in the summary field.

#### 5c — Query the L2 table

```python
l2_col = l2_type  # e.g. "City_Ward"
ALLOWED_COLS = set(hs_cols)

score_col = "<chosen_hs_column>"   # e.g. "hs_camera_expansion_support"
assert score_col in ALLOWED_COLS, f"Column {score_col} not in allowed set"

cur.execute(
    f"""
    SELECT
        SUM(CASE WHEN `{score_col}` >= 50 THEN 1 ELSE 0 END) AS support_count,
        SUM(CASE WHEN `{score_col}` < 50  THEN 1 ELSE 0 END) AS oppose_count,
        COUNT(*) AS total
    FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq
    WHERE `{l2_col}` = :l2_name
      AND Voters_Active = 'A'
    """,
    {"l2_name": l2_name}
)
row = cur.fetchone()
support_count, oppose_count, total = row
support_pct = round(support_count / total * 100, 1) if total else None
oppose_pct  = round(oppose_count  / total * 100, 1) if total else None
```

#### 5d — Format the sentiment summary

The `constituent_sentiment.summary` string must use this format:

```
**{support_pct}% support · {oppose_pct}% oppose**
{One sentence describing what the score means for this jurisdiction, using plain language. Sentiments are not survey results — report them as modeled estimates for that jurisdiction.}
```

Example:
```
**72% support · 28% oppose**
Residents in this district are estimated to support camera expansion for public safety at a notably high rate.
```

When no relevant score exists, set `constituent_sentiment` to `null`. Do not write a fallback text string — null is the correct JSON value.

When reporting sentiment:
- Say: "residents in this district are estimated to..." or "GoodParty.org's data shows that modeled support stands at..."
- Do NOT say: "X% of voters support" (implies a direct survey) or "data shows voters believe" (overstates certainty)
- Ensure `support_pct + oppose_pct` rounds to 100.

### Step 6 — (Conditional) Extract budget impact

For each priority item, scan the agenda packet text for explicit dollar figures. Extract verbatim — do not round, paraphrase, or infer. If no figures are available, set `budget_impact` to `null` for that item.

If you find figures, also look for:
- Per-constituent translation at the local levy level
- Stacked impact if multiple items affect the same taxpayer

Do not report multiple figures in the same sentence — this can cause ambiguity. If discrepancies appear between figures in different source documents, flag them in `budget_impact.summary` rather than resolving silently.

### Step 7 — Assemble the artifact

Assemble the final JSON with three top-level keys: `briefing`, `claims`, `sources`.

**`briefing`** structure:
```json
{
  "official_name": "<officialName from PARAMS>",
  "estimated_read_time_minutes": 8,
  "agenda": [
    {"item_number": 1, "title": "...", "is_priority": true},
    ...
  ],
  "executive_summary": [
    {"item_title": "...", "requires_vote": true, "summary": "..."}
  ],
  "priority_items": [
    {
      "title": "...",
      "overview": "...",
      "constituent_sentiment": null,
      "recent_news": [...],
      "budget_impact": null,
      "key_observations": ["...", "..."]
    }
  ],
  "non_priority_items": [
    {"title": "...", "description": "One sentence describing what it is and what the official should expect."}
  ]
}
```

**Overview field:** Tell the official what is actually at stake — not just what the item is. Where relevant, describe what their silence or inaction would mean. Use neutral, extractive language consistent with the role and voice rules above.

**`key_observations` field:** This section synthesizes — it has a different epistemic status than the rest of the briefing. The global role and voice rules still apply. Up to five bullet points, one or two sentences each.

What makes a useful observation:
- Surfaces a tension or gap in the source materials the official may not have noticed
- Connects constituent sentiment data to a specific aspect of the item
- Notes where a staff recommendation diverges from constituent data or prior council positions
- Flags a question the official might want answered before or during the meeting

Tone examples (these illustrate approach, not templates):
- "Constituent data indicates strong modeled support for the camera expansion district-wide, with notably higher estimated support in the Northside. The proposed location map may be worth reviewing against this distribution ahead of the vote."
- "The agenda packet describes vendor selection as primarily a staff decision. Inferred: the location placement decision is where the council has the most meaningful input — the vote effectively ratifies both together."
- "It may be worth asking staff whether camera locations were weighted by service request volume or by other criteria. The agenda packet does not specify the selection methodology."
- "Staff recommend approving the full contract in a single action. The constituent sentiment data reflects support for camera expansion generally and does not speak to the specific locations proposed — these are distinct questions the vote bundles together."

**`claims`** — flat list, one entry per factual claim in the briefing:
```json
[
  {
    "claim_text": "...",
    "claim_type": "budget number",
    "claim_weight": "high",
    "source_extracts": ["verbatim passage from source"],
    "source_ids": ["src-001"],
    "source_type": "Agenda PDF"
  }
]
```

**`sources`** — full bibliography. For each source capture:
- Source name and URL
- Type (`agenda_packet`, `news`, `haystaq`, `government_website`)
- Date accessed (ISO 8601 timestamp)
- For agenda packet sources: page number and section heading
- For news sources: article type (`reporting` / `opinion` / `editorial`) and publication date

```json
[
  {
    "id": "src-001",
    "name": "City Council Meeting Agenda — 2026-05-13",
    "url": "<agendaUrl>",
    "type": "agenda_packet",
    "date_accessed": "<ISO 8601 timestamp>",
    "page_number": 4,
    "section_heading": "Item 3 — Budget Amendment",
    "article_date": null
  }
]
```

Required disclosure — set `briefing.required_disclosure` to this exact string:

```
This briefing was generated with AI assistance and may contain errors. Inferred or synthesized content represents model-generated interpretation, not verified fact. Constituent sentiment data, where present, reflects modeled estimates for constituents in that jurisdiction.
```

### Step 8 — Write artifact

```python
import json
from datetime import datetime, timezone

artifact = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "briefing": briefing,
    "claims": claims,
    "sources": sources
}

os.makedirs("/workspace/output", exist_ok=True)
with open("/workspace/output/meeting_briefings_experiment_20260513_1155.json", "w") as f:
    json.dump(artifact, f, indent=2)
print("Artifact written.")
```

### Step 9 — Validate

```bash
python3 /workspace/validate_output.py
```

If validation fails, read the error message, fix the artifact in Python, rewrite the file, and re-run. Do not declare success until validation passes.

## Spot-check

After validation passes, verify these manually:

1. **Priority item count**: `briefing.priority_items` has 1–3 items. If 0, you failed to classify any item as priority — re-read the agenda and re-classify.

2. **Claims are traceable**: Pick 3 `claims` at random. Confirm each `claim_text` appears verbatim in the briefing output, each `source_ids` entry resolves to a real entry in `sources`, and each `source_extracts` passage could plausibly come from that source.

3. **Sources resolve**: For each news source, confirm the URL actually loads and the article body is about the agenda item (use `pmf_runtime.http.get(url)` if needed).

4. **Haystaq sentiment sanity**: If any `constituent_sentiment` is populated, confirm `support_pct + oppose_pct` rounds to 100. Confirm the score column name is a real `hs_*` column discovered via `information_schema`. Confirm the summary uses the required bold format. If sentiment appears for an item where no `hs_*` column was found — that's an error, set it to `null`.

5. **No hallucinated claims**: Confirm that no claim in `claims` references a dollar amount, vote count, name, or date that does not appear verbatim in the agenda PDF text or a confirmed news article body.

6. **Key observations quality**: Each `key_observations` entry should do at least one of: surface a tension or gap, connect sentiment to a specific aspect, note a staff/data divergence, or flag a question for the official. Generic summaries that merely restate the overview are not observations — rewrite them.

7. **No advisory language**: Scan `priority_items[*].key_observations` for imperative voice ("Push for", "Ensure that", "Frame your position", "Demand", "Insist"). Replace with neutral or softer language ("You may want to consider...", "It may be worth asking...").

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `ScopeViolation: scope_predicate_override` | Query includes `WHERE Residence_Addresses_State` or `Residence_Addresses_City` | Remove those clauses — broker auto-injects them |
| Databricks 422 repeatedly | Positional `?`, Postgres `FILTER`, `Voters_Active = 1`, or unauthorized table | Recheck CRITICAL RULES; run a minimal test query first |
| All sentiment scores < 5% | Used `= 1` instead of `>= 50` on an `hs_*` column | Re-run with `>= 50` threshold |
| PDF extraction empty | PDF is image-based or http.get returned unexpected content | Inspect `r["body"][:500]` — if bytes look like a PDF header (`%PDF`), encode as latin-1 and retry with pdfplumber |
| News URL 404 or irrelevant | Search snippet was misleading | Use `http.get(url)` to verify before including |
| Validation fails: missing field | A conditional field (sentiment, news, budget) was omitted entirely instead of set to `null` | Set the field to `null` in the object — do not drop the key |
| `priority_items` is empty | No items classified as priority | Re-read classification criteria; "requires a vote" alone qualifies |
| `Runner: No artifact files found` | Ran out of turns before writing | Prioritize writing a partial artifact early, then refine |
