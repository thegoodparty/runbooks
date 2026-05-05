Build the QA layer using the original Runbook QA Spec as the implementation contract, but preserve compatibility with the engineer handoff schema.

Do not simplify claim_type to only factual/modeled/inferred/recommendation/calculation. Keep domain-specific claim_type values like budget_number and date_or_deadline, and add normalized_claim_type for the broader category.

Add risk and verification_category fields from the updated merged spec.

Use final statuses:
pass | regenerate | human_review | block_release

Implement ordered checks:
1. schema validation
2. referential integrity
3. source reachability/snapshot integrity
4. source policy validation
5. claim support classification
6. numeric/date/name copy checks
7. modeled data labeling
8. required data completeness

Emit:
final artifact
audit_bundle.json
sources.json
claims.json
claim_citation_pairs.json
qa_results.json
repair_plan.json when needed
audit log fields

Prioritize compatibility over elegance. Existing fields should remain accepted even if newer fields are added.