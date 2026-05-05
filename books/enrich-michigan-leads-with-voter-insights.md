Enrich a CSV of Michigan elected officials with Haystaq constituent insights and AI-generated polling questions.

## Prerequisites

**scripts/.env variables**: `DATABRICKS_API_KEY`, `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `ANTHROPIC_API_KEY`
**Optional scripts/.env variables**: `GOOGLE_CIVIC_API_KEY` — additional district verification (unused by default)
**Tools**: `uv` (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`), `python 3.12+`
**Setup**: `cd scripts/python && uv sync`

## Input CSV

The input CSV must include these columns:

| Column | Example |
|--------|---------|
| `Record ID` | 39779198735 |
| `First Name` | David |
| `Last Name` | Kreuger |
| `Email` | dakrueger2k@yahoo.com |
| `City` | Swartz Creek |
| `State/Region` | Michigan |
| `Postal Code` | 48473 |
| `Candidate Office` | Swartz Creek City Council - At Large |
| `Office Type` | City Council |

## Steps

1. **Install dependencies**

   ```bash
   cd scripts/python && uv sync
   ```

2. **Verify credentials** — ensure `scripts/.env` has all required variables (see Prerequisites above)

3. **Run the enrichment script**

   ```bash
   cd scripts/python
   uv run enrich_michigan_leads.py /path/to/leads.csv
   ```

   Output defaults to `/path/to/leads-enriched.csv`. To specify explicitly:

   ```bash
   uv run enrich_michigan_leads.py /path/to/leads.csv /path/to/output.csv
   ```

4. **Review output** — each lead gains 10 new columns:
   - `District Zip Codes` — zip codes in the official's jurisdiction
   - `Issue 1`, `Issue 1 Question 1`, `Issue 1 Question 2`
   - `Issue 2`, `Issue 2 Question 1`, `Issue 2 Question 2`
   - `Issue 3`, `Issue 3 Question 1`, `Issue 3 Question 2`

## How It Works

For each lead the script:

1. **Identifies the district** — parses `Candidate Office` to extract the jurisdiction (city, township, or county), then queries the Michigan Haystaq voter database for all zip codes in that jurisdiction
2. **Queries top issues** — aggregates Haystaq issue scores across voters in those zip codes and returns the top 3
3. **Generates polling questions** — calls Claude to generate 2 actionable polling questions per issue, scoped to the office type

**District lookup strategy:**
- Parses jurisdiction from office title (e.g., "Swartz Creek City Council" → "Swartz Creek")
- Queries `stg_dbt_source__l2_s3_mi_uniform` for zip codes in that city
- Falls back to the official's own postal code if the city lookup returns nothing
- For county-level positions, queries all zip codes in that county

## Sample Output

**Before:**
```
Record ID,First Name,Last Name,City,Postal Code,Candidate Office,Office Type
39779198735,David,Kreuger,Swartz Creek,48473,Swartz Creek City Council - At Large,City Council
```

**After (added columns):**
```
District Zip Codes,Issue 1,Issue 1 Question 1,Issue 1 Question 2,...
"48433, 48473, 48509",Education Funding,"What improvements would you most like to see in local schools?","Which programs should receive additional funding?",...
```

## Data Sources

| Table | Content |
|-------|---------|
| `goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_uniform` | Voter demographics and addresses |
| `goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_haystaq_dna_scores` | Issue scores (0–100) |

See `books/query-voter-data.md` for a full reference on Haystaq tables and score interpretation.

## Troubleshooting

**No Haystaq data found for zip codes**
Verify the zip code is in Michigan and has voter data. The script always includes the official's own postal code as a fallback.

**Question generation fails**
Check that `ANTHROPIC_API_KEY` is set in `scripts/.env` and is valid.

**District boundaries unclear**
For school boards, the script extracts the school district name. For city councils, it uses the city name. Non-standard `Candidate Office` formats fall back to the official's postal code.

**Performance**
~2–3 minutes per lead (Databricks + Claude API calls). For large batches (300+ leads), expect 10–15 hours. Test on a small subset first by editing the script to slice the DataFrame: `df = df.head(10)`.
