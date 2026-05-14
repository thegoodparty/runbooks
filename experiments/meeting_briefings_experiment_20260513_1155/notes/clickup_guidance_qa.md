Let's build Governance Briefings that are useful, grounded, auditable, and safe enough to show to incoming elected officials.  Because these briefings may contain factual claims, governance guidance, budget data, modeled community priorities, and tactical recommendations, the system must produce not only a final document but also inspectable intermediate artifacts that allow claims, sources, and generation decisions to be audited.

Outputs Required for lightweight QA 
The pipeline must also produce inspectable intermediate artifacts that allow QA to understand how the briefing was assembled. At the most basic, have agents output:
the final artifact
citations in a predictable syntax
a list of data points it tried to satisfy
sources it used, metadata
claim/citation pairs and source extracts
validation results
 
How to operationalize in runbook-driven process
Generation can be prompt/runbook-driven, but every run must emit a structured audit bundle.
Generally, QA requires schema-valid JSON. Without source snapshots/text, later QA is fragile. Some examples are shared below e.g.:
{
  "runbook_version": "...",
  "briefing_type": "...",
  "required_data_points": [],
  "sources": [],
  "claims": [],
  "claim_citation_pairs": [],
  "draft_sections": [],
  "qa_results": [],
  "final_status": "pass|regenerate|human_review|block_release"
}

Each claim needs stable fields:
{
  "claim_id": "claim_001",
  "section_id": "budget",
  "claim_text": "...",
  "claim_type": "budget_number",
  "citation_ids": ["source_003"], 
  "source_extract": ["extract1 from source_003 substantiating claim_id", "extract2 from source_003 substantiating claim_id"],
  "required_sourc Constituent Sentiment e_type": "official_budget",
  "route_if_unsupported": "block_release"
}

Each source needs more than a URL:
{
  "source_id": "source_003",
  "url": "...",
  "source_type": "official_budget",
  "retrieved_at": "...",
  "title": "...",
  "publisher": "...",
  "retrieved_text_or_snapshot": "..."
}


Each briefing type should have a structured definition to facilitate QA verification.
{
 "briefing_type": "city_budget",
 "required_sections": [
   "budget_at_a_glance",
   "major_spending_categories",
   "community_alignment",
   "questions_to_ask"
 ],
 "required_data_points": [
   {
     "name": "total_operating_budget",
     "required": true,
     "allowed_sources": [
       "official city budget",
       "audited financial report",
       "official city finance page"
     ],
     "citation_required": true
   }
 ]
}
Source rules

Create a table by data type, acceptable sources, and whether or not release should be blocked if claim is unsupported. We already prepared one that could be reused, described here: 
Here's an example of how that table could look.


Important distinction: facts, modeled estimates, and advice need different QA rules.

Checks in QA
The existing QA mostly supports the bolded claim below. But we can expand QA and also check the other items.
Does every required data point exist?
Does every critical claim have a citation?
Is the cited source reachable?
Is the source type allowed?
Does the cited text actually support the claim?
Are numbers/dates/names copied correctly?
Are modeled estimates labeled as modeled?
Did the final status route to pass/regenerate/human review/block?

Proposed Gating policy
Define pass / regenerate / block.
{
 "status": "pass | regenerate | human_review | block_release",
 "reasons": [],
 "failed_checks": []
}

Suggested rules: When there's an unsupported high claim weight item, default to permitting an informed re-generation of briefing or briefing section max 2x with info on QA failure. Absolute failures can be escalated for human review or just dropped from the prototype deployment until we better understand how to handle it (likely via updated generation/QA).

Require targeted repair:

{
 "failed_section": "city_budget",
 "failure_type": "unsupported_budget_number",
 "repair_instruction": "Regenerate only the budget section using official budget sources.",
 "attempt_number": 2
}
Audit log

Require every run to be inspectable later.

Store:

{
 "briefing_id": "...",
 "jurisdiction": "...",
 "official_role": "...",
 "run_timestamp": "...",
 "generator_prompt_version": "...",
 "qa_prompt_version": "...",
 "sources_used": [],
 "claims": [],
 "qa_results": [],
 "final_status": "...",
 "human_review_notes": []
}


