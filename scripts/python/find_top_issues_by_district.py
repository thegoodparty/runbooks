import argparse
import csv
import sys
from pathlib import Path

from databricks_query import execute_query


CURATED_CSV = Path(__file__).parent / "data" / "curated_issue_columns.csv"
TABLE = "goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq"


def load_keepers(path: Path) -> list[dict]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r["keep"].lower() == "true"]


def build_query(state: str, district_col: str, district_name: str, threshold: int, issue_cols: list[str]) -> str:
    aggs = ",\n    ".join(
        f"AVG(CASE WHEN CAST(`{c}` AS DOUBLE) >= {threshold} THEN 1.0 ELSE 0.0 END) * 100 AS `{c}`"
        for c in issue_cols
    )
    state_safe = state.replace("'", "''")
    district_safe = district_name.replace("'", "''")
    return f"""
WITH base AS (
  SELECT *
  FROM {TABLE}
  WHERE state_postal_code = '{state_safe}'
    AND Voters_Active = 'A'
    AND `{district_col}` IS NOT NULL
),
state_baseline AS (
  SELECT COUNT(*) AS state_total, {aggs} FROM base
),
district_pcts AS (
  SELECT COUNT(*) AS district_total, {aggs}
  FROM base
  WHERE `{district_col}` = '{district_safe}'
)
SELECT * FROM district_pcts CROSS JOIN state_baseline
"""


def extract_lift_from_raw(raw_row: tuple, issue_cols: list[str], col_meta: dict, state: str, district_col: str, district_name: str) -> list[dict]:
    n = len(issue_cols)
    district_total = int(raw_row[0])
    state_total = int(raw_row[1 + n])
    out = []
    for i, c in enumerate(issue_cols):
        d_pct = float(raw_row[1 + i] or 0.0)
        s_pct = float(raw_row[1 + n + 1 + i] or 0.0)
        meta = col_meta[c]
        out.append({
            "state": state,
            "district_type": district_col,
            "district": district_name,
            "district_total": district_total,
            "state_total": state_total,
            "column": c,
            "topic": meta["topic"],
            "polarity": meta["polarity"],
            "human_label": meta["human_label"],
            "district_pct": round(d_pct, 2),
            "state_pct": round(s_pct, 2),
            "lift_pct_pts": round(d_pct - s_pct, 2),
        })
    return out


def dedup_by_topic_top_k(rows: list[dict], top_k: int) -> list[dict]:
    by_topic: dict[str, dict] = {}
    for r in sorted(rows, key=lambda x: -x["lift_pct_pts"]):
        if r["topic"] not in by_topic:
            by_topic[r["topic"]] = r
    return sorted(by_topic.values(), key=lambda x: -x["lift_pct_pts"])[:top_k]


def write_long_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Top distinctive campaign issues in an L2 district by lift over state baseline.")
    p.add_argument("--state", required=True, help="Two-letter state postal code, e.g. NC")
    p.add_argument("--district-type", required=True, help="L2 district column, e.g. US_Congressional_District")
    p.add_argument("--district-name", required=True, help="Exact district name as stored in L2, e.g. 12")
    p.add_argument("--top-k", type=int, default=15)
    p.add_argument("--threshold", type=int, default=70)
    p.add_argument("--output", type=Path, help="Optional: write long-format CSV (all curated columns) to this path")
    p.add_argument("--curated-csv", type=Path, default=CURATED_CSV)
    args = p.parse_args(argv)

    keepers = load_keepers(args.curated_csv)
    issue_cols = [r["column"] for r in keepers]
    col_meta = {r["column"]: r for r in keepers}
    print(f"Curated issue columns: {len(issue_cols)}", file=sys.stderr)

    query = build_query(args.state, args.district_type, args.district_name, args.threshold, issue_cols)
    print(f"Querying {args.state} × {args.district_type} = {args.district_name}", file=sys.stderr)

    df = execute_query(query)
    if df.empty:
        print(f"No rows returned. Check that '{args.district_name}' is a valid value in {args.district_type} for state {args.state}.", file=sys.stderr)
        return 2

    raw_row = tuple(df.iloc[0].tolist())
    long_rows = extract_lift_from_raw(raw_row, issue_cols, col_meta, args.state, args.district_type, args.district_name)

    if args.output:
        write_long_csv(long_rows, args.output)
        print(f"Wrote {args.output}", file=sys.stderr)

    ranked = dedup_by_topic_top_k(long_rows, args.top_k)
    total = long_rows[0]["district_total"]

    print(f"\n=== Top {args.top_k} distinctive issues — {args.state} × {args.district_type} = {args.district_name} ({total:,} active voters) ===\n")
    for r in ranked:
        print(f"   {r['lift_pct_pts']:+5.1f}  {r['human_label']:<48} ({r['topic']})")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
