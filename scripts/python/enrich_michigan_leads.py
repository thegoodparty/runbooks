"""Enrich a CSV of Michigan elected officials with Haystaq voter insights and polling questions.

Usage:
    cd scripts/python
    uv run enrich_michigan_leads.py <input_csv> [output_csv]

Arguments:
    input_csv   Path to input CSV (see books/enrich-michigan-leads-with-voter-insights.md for column spec)
    output_csv  Optional output path. Defaults to <input_stem>-enriched<input_suffix>

Required (scripts/.env):
    DATABRICKS_API_KEY, DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH
    ANTHROPIC_API_KEY

Optional (scripts/.env):
    GOOGLE_CIVIC_API_KEY — additional district verification (unused by default)
"""
import os
import re
import sys
from pathlib import Path

import anthropic
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from databricks_query import execute_query


def _parse_jurisdiction(candidate_office: str, city: str) -> str:
    """Extract jurisdiction name from Candidate Office string."""
    patterns = [
        r'(.+?)\s+City Council',
        r'(.+?)\s+Village Board',
        r'(.+?)\s+Township Board',
        r'(.+?)\s+City Commission',
        r'(.+?)\s+City Mayor',
        r'(.+?)\s+Village President',
        r'(.+?)\s+City Clerk',
        r'(.+?)\s+City Treasurer',
    ]
    for pattern in patterns:
        m = re.search(pattern, candidate_office, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    if 'School Board' in candidate_office or 'School District' in candidate_office:
        m = re.search(r'(.+?)\s+(?:Area |Community |Public |Consolidated |Union )?School', candidate_office)
        if m:
            return m.group(1).strip()

    return city


def _zips_for_city(city: str) -> list[str]:
    query = """
        SELECT DISTINCT Residence_Addresses_Zip
        FROM goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_uniform
        WHERE UPPER(Residence_Addresses_City) = ?
          AND Residence_Addresses_Zip IS NOT NULL
          AND Residence_Addresses_Zip != ''
        ORDER BY Residence_Addresses_Zip
    """
    try:
        result = execute_query(query, [city.upper()])
        return list(set(str(z)[:5] for z in result['Residence_Addresses_Zip'] if z and str(z).strip()))
    except Exception as e:
        print(f"  Warning: city zip lookup failed for {city}: {e}")
        return []


def _zips_for_county(county: str) -> list[str]:
    query = """
        SELECT DISTINCT Residence_Addresses_Zip
        FROM goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_uniform
        WHERE UPPER(Residence_Addresses_County) = ?
          AND Residence_Addresses_Zip IS NOT NULL
          AND Residence_Addresses_Zip != ''
        ORDER BY Residence_Addresses_Zip
    """
    try:
        result = execute_query(query, [county.upper()])
        return list(set(str(z)[:5] for z in result['Residence_Addresses_Zip'] if z and str(z).strip()))
    except Exception as e:
        print(f"  Warning: county zip lookup failed for {county}: {e}")
        return []


def get_district_zips(candidate_office: str, city: str, postal_code: str) -> list[str]:
    """Determine district zip codes from Haystaq data."""
    all_zips: set[str] = set()
    if postal_code and str(postal_code).strip():
        all_zips.add(str(postal_code)[:5])

    jurisdiction = _parse_jurisdiction(candidate_office, city)
    print(f"  Jurisdiction: {jurisdiction}")

    city_zips = _zips_for_city(jurisdiction)
    if city_zips:
        print(f"  Found {len(city_zips)} zip(s) in {jurisdiction}")
        all_zips.update(city_zips)
    elif city and city != jurisdiction:
        fallback = _zips_for_city(city)
        if fallback:
            print(f"  Found {len(fallback)} zip(s) via fallback city {city}")
            all_zips.update(fallback)

    if 'County' in candidate_office:
        m = re.search(r'(.+?)\s+County', candidate_office)
        if m:
            county = m.group(1).strip()
            county_zips = _zips_for_county(county)
            if county_zips:
                print(f"  Found {len(county_zips)} zip(s) in {county} County")
                all_zips.update(county_zips)

    return sorted(all_zips)


_ISSUE_LABELS = {
    'affordable_housing':   'Affordable Housing',
    'environment':          'Environmental Protection',
    'economics':            'Economic Policy',
    'education':            'Education Funding',
    'healthcare':           'Healthcare Access',
    'public_safety':        'Public Safety',
    'tax_increase':         'Tax Policy',
    'universal_healthcare': 'Universal Healthcare',
    'mental_health':        'Mental Health Services',
    'public_transit':       'Public Transportation',
    'minimum_wage':         'Minimum Wage',
}


def get_top_issues(zip_codes: list[str], top_n: int = 3) -> list[tuple[str, float]]:
    """Query Haystaq for the top N issues across given zip codes."""
    if not zip_codes:
        return []

    zip_list = "', '".join(zip_codes)
    query = f"""
        SELECT
            AVG(CAST(s.hs_affordable_housing_gov_has_role AS DOUBLE))          as affordable_housing,
            AVG(CAST(s.hs_most_important_policy_item_environment AS DOUBLE))   as environment,
            AVG(CAST(s.hs_most_important_policy_item_economics AS DOUBLE))     as economics,
            AVG(CAST(s.hs_most_important_policy_item_education AS DOUBLE))     as education,
            AVG(CAST(s.hs_most_important_policy_item_healthcare AS DOUBLE))    as healthcare,
            AVG(CAST(s.hs_most_important_policy_item_crime AS DOUBLE))         as public_safety,
            AVG(CAST(s.hs_tax_increase_for_services_support AS DOUBLE))        as tax_increase,
            AVG(CAST(s.hs_universal_healthcare_support AS DOUBLE))             as universal_healthcare,
            AVG(CAST(s.hs_mental_health_services_support AS DOUBLE))           as mental_health,
            AVG(CAST(s.hs_public_transit_expansion_support AS DOUBLE))         as public_transit,
            AVG(CAST(s.hs_minimum_wage_increase_support AS DOUBLE))            as minimum_wage
        FROM goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_uniform u
        JOIN goodparty_data_catalog.dbt.stg_dbt_source__l2_s3_mi_haystaq_dna_scores s
          ON u.LALVOTERID = s.LALVOTERID
        WHERE u.Residence_Addresses_Zip IN ('{zip_list}')
    """
    try:
        result = execute_query(query)
        if result.empty:
            return []
        row = result.iloc[0]
        issues = [
            (_ISSUE_LABELS[col], float(row[col]))
            for col in _ISSUE_LABELS
            if col in row and pd.notna(row[col])
        ]
        issues.sort(key=lambda x: x[1], reverse=True)
        return issues[:top_n]
    except Exception as e:
        print(f"  Warning: issue query failed: {e}")
        return []


def generate_questions(issue: str, office_type: str, client: anthropic.Anthropic) -> tuple[str, str]:
    """Generate 2 polling questions for an issue using Claude."""
    prompt = (
        f"You are helping a {office_type} official create polling questions about {issue}.\n\n"
        "Generate 2 specific, actionable polling questions that:\n"
        "1. Help the official understand constituent concerns\n"
        "2. Are clear and neutral (not leading)\n"
        "3. Gather insights that inform policy decisions\n"
        f"4. Are scoped to a {office_type} role (local government, not federal)\n\n"
        "Format:\nQuestion 1: [question]\nQuestion 2: [question]"
    )
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text
        q1 = q2 = "[Could not parse question]"
        for line in text.splitlines():
            if line.startswith("Question 1:"):
                q1 = line.replace("Question 1:", "").strip()
            elif line.startswith("Question 2:"):
                q2 = line.replace("Question 2:", "").strip()
        return q1, q2
    except Exception as e:
        print(f"  Warning: question generation failed for {issue}: {e}")
        return "[Error generating question]", "[Error generating question]"


def enrich_lead(row: pd.Series, anthropic_client: anthropic.Anthropic) -> dict:
    zip_codes = get_district_zips(
        str(row.get('Candidate Office', '')),
        str(row.get('City', '')),
        str(row.get('Postal Code', '')),
    )
    top_issues = get_top_issues(zip_codes)

    result: dict = {'District Zip Codes': ', '.join(zip_codes)}
    for i, (issue_name, _) in enumerate(top_issues, 1):
        q1, q2 = generate_questions(issue_name, str(row.get('Office Type', 'Local')), anthropic_client)
        result[f'Issue {i}'] = issue_name
        result[f'Issue {i} Question 1'] = q1
        result[f'Issue {i} Question 2'] = q2
    for i in range(len(top_issues) + 1, 4):
        result[f'Issue {i}'] = ''
        result[f'Issue {i} Question 1'] = ''
        result[f'Issue {i} Question 2'] = ''
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: uv run enrich_michigan_leads.py <input_csv> [output_csv]')
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = (
        Path(sys.argv[2]) if len(sys.argv) > 2
        else input_path.parent / f"{input_path.stem}-enriched{input_path.suffix}"
    )

    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} leads from {input_path}\n")

    anthropic_client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

    enriched_rows = []
    for idx, row in df.iterrows():
        print(f"[{idx + 1}/{len(df)}] {row.get('First Name', '')} {row.get('Last Name', '')} — {row.get('Candidate Office', '')}")
        try:
            enriched_rows.append(enrich_lead(row, anthropic_client))
        except Exception as e:
            print(f"  Error: {e}")
            empty: dict = {'District Zip Codes': ''}
            for i in range(1, 4):
                empty[f'Issue {i}'] = ''
                empty[f'Issue {i} Question 1'] = ''
                empty[f'Issue {i} Question 2'] = ''
            enriched_rows.append(empty)

    output_df = pd.concat([df, pd.DataFrame(enriched_rows)], axis=1)
    output_df.to_csv(output_path, index=False)
    print(f"\nDone — {len(output_df)} leads enriched → {output_path}")


if __name__ == '__main__':
    main()
