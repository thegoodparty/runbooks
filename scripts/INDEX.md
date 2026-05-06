# Script Index

Quick reference for all available scripts. Keep this updated when adding or removing scripts.

| Script | Description | Used By |
|--------|-------------|---------|
| `python/databricks_query.py` | Execute SQL queries against Databricks and return results as a DataFrame | books/query-voter-data.md |
| `python/circle_query.py` | GET wrapper for the Circle Admin API v2 (Bearer auth). CLI prints JSON; `get()` helper for programmatic use | books/connect-circle-api.md |
| `python/circle_engagement.py` | Full engagement snapshot — DAU/WAU/MAU, stickiness, contribution mix, content rate, top spaces/contributors, cohort retention | books/circle-engagement-snapshot.md |
| `python/qa_init.py` | Scaffold `output/` with stub artifact files before a generation run | books/qa-protocol.md |
| `python/qa_validate.py` | Validate a completed `output/` folder — checks structure, referential integrity, and source coverage; writes `qa_results.json` and `repair_plan.json` | books/qa-protocol.md |
