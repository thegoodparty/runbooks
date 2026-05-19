import os
import sys
from pathlib import Path
import pandas as pd
from databricks.sql import connect
from dotenv import load_dotenv

# scripts/.env is the in-repo convention. In Fargate the task definition populates
# os.environ at task launch and no .env file is needed; load_dotenv is a no-op when
# the file is missing. Locally, contributors keep credentials in scripts/.env (real
# file or symlink — python-dotenv handles both, including broken symlinks, without
# crashing).
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


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
