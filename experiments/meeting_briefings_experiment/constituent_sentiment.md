A primer on Haystaq scores and how to present sentiment data in the briefing.

Reference: https://haystaqdna.com/wp-content/uploads/2024/10/L2-National-Models-User-Guide-2024-Updated-w-Com.pdf

Data dictionary: [Databricks link TBD]

## What Haystaq scores are

Modeled voter attitudes on a 0-100 scale derived from L2 voter file data. These are not survey results -- they are modeled estimates based on a national survey.

## When to use Haystaq data

Only include constituent sentiment when a Haystaq score exists that reasonably maps to a priority agenda item. If no relevant score exists, omit this section for that item entirely. Do not substitute general assumptions, national averages, or invented sentiment.

## Sentiment format

Do not surface raw numeric scores. Use tiered language based on the following thresholds:

| Score | Language |
|---|---|
| ≥ 75 | "strong support" / "strong concern" |
| ≥ 60 | "moderate support" / "moderate concern" |
| ≥ 50 | "mixed or slight support" / "mixed or slight concern" |
| < 50 | Do not characterize as supportive or concerned |

Always include this provenance note when constituent data appears:
> "Issue prioritization is based on modeled estimates of constituent sentiment and should be interpreted as directional, not precise."

## What to say / what not to say

Say: "residents in this district are estimated to...", "GoodParty.org's data shows modeled support is..."
Do not say: "X% of voters support" (implies a direct survey), "data shows voters believe" (overstates certainty)
