import os
import sys
from pathlib import Path
import pandas as pd
from databricks.sql import connect
from dotenv import load_dotenv

# scripts/.env is the in-repo convention (symlinked to ~/Research/.env). Fall back
# to ~/Research/.env directly when the symlink is missing — git worktree add does
# not carry untracked symlinks.
for _env_candidate in (
    Path(__file__).resolve().parent.parent / ".env",
    Path.home() / "Research" / ".env",
):
    if _env_candidate.exists() or _env_candidate.is_symlink():
        load_dotenv(_env_candidate)
        break


def execute_query(query: str) -> pd.DataFrame:
    conn = connect(
        server_hostname=os.environ['DATABRICKS_SERVER_HOSTNAME'],
        http_path=os.environ['DATABRICKS_HTTP_PATH'],
        access_token=os.environ['DATABRICKS_TOKEN'],
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: uv run databricks_query.py "SELECT ..."')
        sys.exit(1)
    print(execute_query(sys.argv[1]).to_string())
