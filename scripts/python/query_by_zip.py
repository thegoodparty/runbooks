import sys
from databricks_query import execute_query

VALID_STATE_CODES = {
    'al','ak','az','ar','ca','co','ct','de','fl','ga','hi','id','il','in','ia',
    'ks','ky','la','me','md','ma','mi','mn','ms','mo','mt','ne','nv','nh','nj',
    'nm','ny','nc','nd','oh','ok','or','pa','ri','sc','sd','tn','tx','ut','vt',
    'va','wa','wv','wi','wy'
}

if len(sys.argv) < 3:
    print('Usage: uv run query_by_zip.py CITY_NAME STATE_CODE')
    print('Example: uv run query_by_zip.py CHARLOTTE nc')
    sys.exit(1)

city_name = sys.argv[1].upper()
state_code = sys.argv[2].lower()

if state_code not in VALID_STATE_CODES:
    print(f'Error: invalid state code "{state_code}". Use a two-letter lowercase state code (e.g. nc, il, co).')
    sys.exit(1)

result = execute_query(f'''
    SELECT
        u.Residence_Addresses_Zip as zip,
        COUNT(*) as voter_count,
        AVG(CAST(s.hs_affordable_housing_gov_has_role AS DOUBLE)) as housing_gov_role,
        AVG(CAST(s.hs_most_important_policy_item_environment AS DOUBLE)) as env_priority,
        AVG(CAST(s.hs_most_important_policy_item_economics AS DOUBLE)) as econ_priority,
        AVG(CAST(s.hs_ideology_general_conservative AS DOUBLE)) as ideology_conservative
    FROM goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_{state_code}_uniform u
    JOIN goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_{state_code}_haystaq_dna_scores s
      ON u.LALVOTERID = s.LALVOTERID
    WHERE UPPER(u.Residence_Addresses_City) = ?
    GROUP BY u.Residence_Addresses_Zip
    ORDER BY voter_count DESC
''', [city_name])

print(result.to_string())
