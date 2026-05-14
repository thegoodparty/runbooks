Haystaq scores are modeled estimates of voter sentiment, not direct survey results.

Reference: https://haystaqdna.com/wp-content/uploads/2024/10/L2-National-Models-User-Guide-2024-Updated-w-Com.pdf

The available score metadata lives in the Haystaq data dictionary in Databricks. The agent may use the dictionary to decide which score, if any, is germane to a priority agenda item. The agent should not guess what a score means from its column name alone if the dictionary provides a fuller definition or interpretation note. However, `source_question` may be missing for some rows. When that happens, it is acceptable to infer cautiously from the column name, `proper_column_name`, `description`, `score_high_means`, and `aggregation_guidance` if the match still appears defensible.

## What Haystaq scores are

Most Haystaq issue scores are modeled estimates on a 0-100 scale. In general, higher scores indicate a greater modeled likelihood that voters in that geography hold the position named in the score definition. Some fields are `raw score` fields, not normalized issue scores. Do not use raw score fields in the briefing unless no standard issue score exists and the dictionary explicitly supports interpretation. Prefer dictionary fields that have usable values in `description`, `score_high_means`, and `aggregation_guidance`.

## When to use Haystaq data

Use constituent sentiment only for a priority item, and only if the agent can identify a score that is meaningfully related to the substance of that item.

This is a selection task before it is a writing task:

1. Read the agenda item and supporting packet materials.
2. Identify the actual policy question at issue, not just the broad topic area.
3. Review the Haystaq data dictionary for candidate scores that could bear on that question.
4. Select up to three candidate scores that appear most germane to the item.
5. Bring forward the score metadata needed to interpret those candidates, especially `description`, `score_high_means`, and `aggregation_guidance`.
6. Query the jurisdiction values for those candidates.
7. Report only one score in the final briefing: the single score that best captures the most relevant constituent signal for that agenda item.

If the dictionary search reveals one or more defensible candidate scores, the briefing should report one score. Do not suppress the section simply because the resulting modeled value is middling. The threshold for reporting is relevance of the score-item match, not extremity of the returned number.

Do not include constituent sentiment when:
- the only candidate scores are too broad or only loosely related to the item
- the dictionary entry is incomplete enough that the score cannot be interpreted safely
- the best available field is a raw score or subgroup-only field that does not support clean jurisdiction-level interpretation
- the item is procedural, ceremonial, or too narrow for a defensible sentiment mapping

## How to determine whether a score is relevant

Prefer scores where the dictionary shows a direct relationship to the action under consideration. Use the score's `description`, `source_question`, `dependent_variable`, `score_high_means`, and `aggregation_guidance`.

Good matches:
- use issue scores that map directly onto the policy question before council
- prefer a score that reflects the substance of the item rather than a generic worldview or ideology measure
- when only a broader proxy exists, use it only if the agent can clearly describe the score as a general measure related to the issue rather than a direct measure of the specific proposal

Weak matches that should usually be rejected:
- a broad ideology score when a direct issue score exists
- a general "helping people" or values measure when the item is a specific zoning or procurement action
- a score that is only adjacent to the topic but does not map to the actual decision being made

If multiple scores seem plausible, shortlist no more than three. After querying those three, choose the single score that is most decision-relevant, most interpretable to a reader, and most defensible for the item. Do not stack multiple Haystaq scores into the briefing section. The current briefing format supports one reported Haystaq column per item.

When choosing the one score to report, prioritize:
1. direct relevance to the actual decision before council
2. clarity of interpretation from the dictionary
3. usefulness for helping distinguish whether constituents lean toward or against the policy direction at issue
4. meaningful district divergence from the city overall, when present

## Query workflow

The agent has access to:
- `goodparty_data_catalog.sandbox.haystaq_data_dictionary`
- `goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq`

Use the dictionary first. Only query the wide uniform table after selecting no more than three candidate scores.

### Step 1: inspect dictionary candidates

Start by retrieving candidate dictionary rows for the agenda item's issue area. Use agenda-specific keywords, not just one generic topic word. The query below is illustrative; adapt the keyword filter to the actual item.

```sql
SELECT
  column_name,
  proper_column_name,
  description,
  source_question,
  dependent_variable,
  model_type,
  notes,
  flag_threshold_positive,
  flag_threshold_negative,
  score_high_means,
  is_subgroup_only,
  complementary_field,
  aggregation_guidance
FROM goodparty_data_catalog.sandbox.haystaq_data_dictionary
WHERE
  lower(coalesce(proper_column_name, '')) LIKE '%housing%'
  OR lower(coalesce(description, '')) LIKE '%housing%'
  OR lower(coalesce(source_question, '')) LIKE '%housing%'
ORDER BY
  CASE
    WHEN lower(coalesce(model_type, '')) LIKE '%score (0%' THEN 0
    WHEN lower(coalesce(model_type, '')) LIKE '%raw%' THEN 2
    ELSE 1
  END,
  column_name;
```

After reviewing the returned rows:
- prefer `score (0-100)` style issue scores
- avoid `raw score` unless there is no better option and the dictionary clearly explains how to use it
- avoid `is_subgroup_only = yes`
- use `description` first, then `score_high_means` and `dependent_variable`, to understand what the score represents
- expect `source_question` to be missing on some rows; that is not, by itself, a reason to reject a score
- stop at no more than three candidate scores per item

### Step 2: retrieve the jurisdiction values for the shortlisted scores

Once the candidate scores are chosen, query the district and city averages together so the agent can compare the official's district with the city overall before deciding which single score to report.

Replace:
- `{{SCORE_1}}`, `{{SCORE_2}}`, `{{SCORE_3}}` with up to three selected Haystaq columns
- `{{L2_DISTRICT_TYPE}}` with the allowed district column name from input, for example `City_Ward`
- `{{L2_DISTRICT_NAME}}` with the jurisdiction's district value
- `{{CITY}}` with the input city name

IMPORTANT: The district filtering logic below is a draft and must be validated with the data team before operational use. In particular, confirm that `l2DistrictType` is always a valid column in `goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq`, and confirm the correct `WHERE` behavior for combining district and city scope.

Illustrative version:

```sql
WITH scoped AS (
  SELECT
    CASE
      WHEN {{L2_DISTRICT_TYPE}} = '{{L2_DISTRICT_NAME}}' THEN 'district'
      WHEN upper(Residence_Addresses_City) = upper('{{CITY}}') THEN 'city'
      ELSE NULL
    END AS geography_scope,
    CAST({{SCORE_1}} AS DOUBLE) AS score_1,
    CAST({{SCORE_2}} AS DOUBLE) AS score_2,
    CAST({{SCORE_3}} AS DOUBLE) AS score_3
  FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq
  WHERE
    upper(Residence_Addresses_City) = upper('{{CITY}}')
    OR {{L2_DISTRICT_TYPE}} = '{{L2_DISTRICT_NAME}}'
)
SELECT
  geography_scope,
  ROUND(AVG(score_1), 1) AS avg_score_1,
  ROUND(AVG(score_2), 1) AS avg_score_2,
  ROUND(AVG(score_3), 1) AS avg_score_3,
  COUNT(*) AS voter_count
FROM scoped
WHERE geography_scope IS NOT NULL
GROUP BY geography_scope
ORDER BY CASE geography_scope WHEN 'district' THEN 0 ELSE 1 END;
```

More operational version, still requiring validation of `{{L2_DISTRICT_TYPE}}` before use:

```sql
WITH city_scope AS (
  SELECT
    'city' AS geography_scope,
    CAST({{SCORE_1}} AS DOUBLE) AS score_1,
    CAST({{SCORE_2}} AS DOUBLE) AS score_2,
    CAST({{SCORE_3}} AS DOUBLE) AS score_3
  FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq
  WHERE upper(Residence_Addresses_City) = upper('{{CITY}}')
),
district_scope AS (
  SELECT
    'district' AS geography_scope,
    CAST({{SCORE_1}} AS DOUBLE) AS score_1,
    CAST({{SCORE_2}} AS DOUBLE) AS score_2,
    CAST({{SCORE_3}} AS DOUBLE) AS score_3
  FROM goodparty_data_catalog.dbt.int__l2_nationwide_uniform_w_haystaq
  WHERE {{L2_DISTRICT_TYPE}} = '{{L2_DISTRICT_NAME}}'
)
SELECT
  geography_scope,
  ROUND(AVG(score_1), 1) AS avg_score_1,
  ROUND(AVG(score_2), 1) AS avg_score_2,
  ROUND(AVG(score_3), 1) AS avg_score_3,
  COUNT(*) AS voter_count
FROM (
  SELECT * FROM city_scope
  UNION ALL
  SELECT * FROM district_scope
) combined
GROUP BY geography_scope
ORDER BY CASE geography_scope WHEN 'district' THEN 0 ELSE 1 END;
```

### Step 3: interpret the results

Use the dictionary's own guidance when interpreting the number:
- if `aggregation_guidance` says use the mean score per district, do that
- if `score_high_means` says higher values indicate support for the stated position, present the score as modeled support for that position
- if one shortlisted score is more directly tied to the agenda item's actual decision than the others, prefer that one even if another score has a somewhat stronger raw value
- if the scores are broad proxies rather than direct issue measures, the agent should be conservative when characterizing them, but if the dictionary search found a defensible candidate score, one score should still be reported

Scores around these levels often support restrained interpretation:
- above ~60: meaningful modeled lean toward the stated position
- below ~40: meaningful lean against the stated position
- middle range: mixed or less decisive modeled sentiment

Treat those as interpretation aids, not absolute rules, and defer to the dictionary when it offers more specific guidance.

The final writeup should convert the chosen score into a support-lean or opposition-lean framing based on the selected field's meaning. Example:
- if the chosen field is a pro-policy field and the mean is high, report modeled support
- if the chosen field is an anti-policy field and the mean is high, report modeled opposition to the policy direction
- if the chosen field is a broader proxy, name it as such, for example a broader measure of sentiment on the surrounding issue area rather than direct support for the exact proposal

Do not pretend to have both sides of the distribution if only one score was queried and interpreted. The agent should use the chosen score's orientation and the dictionary language to characterize modeled sentiment faithfully.

## Sentiment format

The briefing's `constituent_sentiment` field should be used conservatively and should primarily reflect the citywide result for the chosen score, with district-level difference surfaced in `district_note` when the district meaningfully departs from the city.

Preferred output shape:

**Modeled sentiment: support-leaning**
Citywide modeled support on this measure is 72 on a 0-100 scale. Ward-level sentiment runs above the citywide estimate.

Alternative:

**Modeled sentiment: opposition-leaning**
Citywide modeled opposition on this measure is 61 on a 0-100 scale. District and city estimates are closely aligned.

Broader proxy example:

**Modeled sentiment: general issue-area support**
Citywide modeled support for the broader issue area measured by this score is 58 on a 0-100 scale. The score does not measure sentiment on the exact proposal directly.

If no relevant data is available:

`constituent_sentiment: null`

Do not force a sentiment section for every priority item.

## What to say / what not to say

Say:
- "Haystaq's district-level model suggests..."
- "Citywide modeled support on this measure is estimated at..."
- "Citywide modeled opposition on this measure is estimated at..."
- "This score reflects a broader issue-area measure, not a direct reading on the exact proposal."
- "This score is a modeled estimate on a 0-100 scale."
- "District-level modeled sentiment on this measure is higher than the citywide estimate."
- "This is a modeled estimate, not a direct survey result."

Do not say:
- "X% of voters support..." since the source is not from an actual survey, but modeled estimates based on a national survey
- "Residents believe..." or "voters think..." as a statement of fact
- "The data proves..." or any language that overstates certainty

## Writing guardrails

- Only include constituent sentiment when the score-item mapping is defensible.
- The agent may query up to three candidate scores but may report only one score per item.
- Prefer citywide figures for the reported score and use district as a comparison note when the district differs meaningfully.
- If the district and city differ meaningfully, that should be noted in `district_note`.
- If the mapping is weak but still defensible from the dictionary, report the single best available score cautiously rather than omitting it.
- Do not force the chosen score into a fake two-sided percentage split unless a true complementary measure has also been retrieved and interpreted.
- Always disclose that the figures are modeled estimates.
