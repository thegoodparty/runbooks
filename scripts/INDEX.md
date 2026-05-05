# Script Index

Quick reference for all available scripts. Keep this updated when adding or removing scripts.

| Script | Description | Used By |
|--------|-------------|---------|
| `python/databricks_query.py` | Execute SQL queries against Databricks and return results as a DataFrame | books/query-voter-data.md, books/generate-elected-official-briefing.md |
| `python/query_demographics.py` | Query voter demographics for a city (total voters, party, age, gender) | books/generate-elected-official-briefing.md |
| `python/query_issue_scores.py` | Query aggregate Haystaq issue scores for a city (local/state issues only) | books/generate-elected-official-briefing.md |
| `python/query_by_zip.py` | Query top issue scores segmented by zip code for a city | books/generate-elected-official-briefing.md |
| `python/enrich_michigan_leads.py` | Enrich a CSV of Michigan leads with Haystaq voter insights and Claude-generated polling questions | books/enrich-michigan-leads-with-voter-insights.md |
| `python/generate_briefing_pdf.py` | Convert a markdown briefing file to a professionally formatted PDF | books/generate-elected-official-briefing.md |
| `python/circle_query.py` | GET wrapper for the Circle Admin API v2 (Bearer auth). CLI prints JSON; `get()` helper for programmatic use | books/connect-circle-api.md |
| `python/circle_engagement.py` | Full engagement snapshot — DAU/WAU/MAU, stickiness, contribution mix, content rate, top spaces/contributors, cohort retention | books/circle-engagement-snapshot.md |
