import os
import sys
from typing import Any
import pandas as pd
from databricks.sql import connect
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

VALID_STATE_CODES = frozenset({
    'al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'fl', 'ga',
    'hi', 'id', 'il', 'in', 'ia', 'ks', 'ky', 'la', 'me', 'md',
    'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne', 'nv', 'nh', 'nj',
    'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc',
    'sd', 'tn', 'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy', 'dc',
})


def normalize_state_code(state_code: str) -> str:
    normalized = state_code.lower()
    if normalized not in VALID_STATE_CODES:
        raise ValueError('STATE_CODE must be a valid 2-letter US state code.')
    return normalized


def execute_query(query: str, parameters: dict[str, Any] | None = None) -> pd.DataFrame:
    conn = connect(
        server_hostname=os.environ['DATABRICKS_SERVER_HOSTNAME'],
        http_path=os.environ['DATABRICKS_HTTP_PATH'],
        access_token=os.environ['DATABRICKS_API_KEY'],
    )
    try:
        with conn.cursor() as cursor:
            if parameters is None:
                cursor.execute(query)
            else:
                cursor.execute(query, parameters=parameters)
            columns = [desc[0] for desc in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
    finally:
        conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: uv run databricks_query.py "SELECT ..."')
        sys.exit(1)
    print(execute_query(sys.argv[1]).to_string())
