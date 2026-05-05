# Script Index

Quick reference for all available scripts. Keep this updated when adding or removing scripts.

| Script | Description | Used By |
|--------|-------------|---------|
| `python/databricks_query.py` | Execute SQL queries against Databricks and return results as a DataFrame | books/query-voter-data.md |
| `python/find_top_issues_by_district.py` | Compute top distinctive campaign issues in an L2 district by lift over state baseline, using the curated 106-column issue list | books/find-top-issues-by-district.md |
| `python/data/curated_issue_columns.csv` | Curated 106-keeper Haystaq issue column list (column, topic, polarity, human_label, keep, drop_reason) — seed data for the lift script | books/find-top-issues-by-district.md |
| `python/circle_query.py` | GET wrapper for the Circle Admin API v2 (Bearer auth). CLI prints JSON; `get()` helper for programmatic use | books/connect-circle-api.md |
| `python/circle_engagement.py` | Full engagement snapshot — DAU/WAU/MAU, stickiness, contribution mix, content rate, top spaces/contributors, cohort retention | books/circle-engagement-snapshot.md |
