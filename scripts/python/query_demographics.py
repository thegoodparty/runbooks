import sys
from databricks_query import execute_query

VALID_STATE_CODES = {
    'al','ak','az','ar','ca','co','ct','de','fl','ga','hi','id','il','in','ia',
    'ks','ky','la','me','md','ma','mi','mn','ms','mo','mt','ne','nv','nh','nj',
    'nm','ny','nc','nd','oh','ok','or','pa','ri','sc','sd','tn','tx','ut','vt',
    'va','wa','wv','wi','wy'
}

if len(sys.argv) < 3:
    print('Usage: uv run query_demographics.py CITY_NAME STATE_CODE')
    print('Example: uv run query_demographics.py CHARLOTTE nc')
    sys.exit(1)

city_name = sys.argv[1].upper()
state_code = sys.argv[2].lower()

if state_code not in VALID_STATE_CODES:
    print(f'Error: invalid state code "{state_code}". Use a two-letter lowercase state code (e.g. nc, il, co).')
    sys.exit(1)

result = execute_query(f'''
    SELECT
        COUNT(DISTINCT LALVOTERID) as total_voters,
        COUNT(DISTINCT CASE WHEN Parties_Description LIKE "%Democrat%" THEN LALVOTERID END) as democrats,
        COUNT(DISTINCT CASE WHEN Parties_Description LIKE "%Republican%" THEN LALVOTERID END) as republicans,
        COUNT(DISTINCT CASE WHEN Parties_Description LIKE "%Unaffiliated%"
                           OR Parties_Description LIKE "%Independent%" THEN LALVOTERID END) as independents,
        ROUND(AVG(CAST(Voters_Age AS INT)), 1) as avg_age,
        COUNT(DISTINCT CASE WHEN Voters_Gender = "M" THEN LALVOTERID END) as male,
        COUNT(DISTINCT CASE WHEN Voters_Gender = "F" THEN LALVOTERID END) as female
    FROM goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_{state_code}_uniform
    WHERE UPPER(Residence_Addresses_City) = ?
''', [city_name])

print(result.to_string())
