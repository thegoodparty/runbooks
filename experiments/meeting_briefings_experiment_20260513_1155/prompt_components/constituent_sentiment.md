A primer on Haystaq scores, which are modeled estimates of voter sentiment based on a national survey. 

Reference: https://haystaqdna.com/wp-content/uploads/2024/10/L2-National-Models-User-Guide-2024-Updated-w-Com.pdf

The data dictionary here may have additional information about the score in databricks https://dbc-3d8ca484-79f3.cloud.databricks.com/explore/data/goodparty_data_catalog/sandbox/haystaq_data_dictionary .

## What Haystaq scores are

Modeled voter attitudes are on a 0-100 scale derived from L2 voter file data. 

## When to use Haystaq data

Scan the Haystaq data source and data dictionary. Only include constituent sentiment if a Haystaq score exists that is reasonably related to the priority agenda item.  

## Sentiment format

Use the Haystaq data dictionary for context on how a score was modeled and what the numbers mean for support vs. opposition or alignment. Include district-level specificity if available. Sentiments are not survey results --report them as modeled estimates for that jurisdiction.

Example:
**72% support · 28% oppose**
Northside support for expanding cameras for public safety climbs to 81%.

When no relevant data is available:
No sentiment data available for [item name]. 
 
## What to say / what not to say

Say: "residents in this district are estimated to...", "GoodParty.org's data shows that modeled support stands at..."
Do not say: "X% of voters support" (implies a direct survey), "data shows voters believe" (overstates certainty)

