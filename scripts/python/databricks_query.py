"""Run a Databricks SQL query and print results as a tab-aligned table.

Env vars (Databricks SDK naming convention):
  DATABRICKS_HOST       — workspace hostname, e.g. adb-xxxx.azuredatabricks.net
  DATABRICKS_HTTP_PATH  — warehouse path, e.g. /sql/1.0/warehouses/xxxx
  DATABRICKS_TOKEN      — personal access token, e.g. dapi_xxxx

Load order (later overrides earlier):
  1. ~/Research/.env (shared cross-project secrets)
  2. <repo>/scripts/.env (project-local override)
"""

import os
import sys
from pathlib import Path

import pandas as pd
from databricks.sql import connect
from dotenv import load_dotenv

# Load shared first, then project-local override.
load_dotenv(Path.home() / "Research" / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            f"Set it in ~/Research/.env or <repo>/scripts/.env "
            f"(see scripts/.env.example for the expected keys)."
        )
    return value


def execute_query(query: str) -> pd.DataFrame:
    conn = connect(
        server_hostname=_require("DATABRICKS_HOST"),
        http_path=_require("DATABRICKS_HTTP_PATH"),
        access_token=_require("DATABRICKS_TOKEN"),
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: uv run databricks_query.py "SELECT ..."')
        sys.exit(1)
    print(execute_query(sys.argv[1]).to_string())
