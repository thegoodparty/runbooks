# Runbook QA Spec

Specification for QA and referential integrity in runbook-driven agent workflows.

## Purpose

Runbooks can be used for simple operational procedures, but they can also drive agents that research new data and generate intelligence products such as governor orientation briefings, meeting briefings, voter reports, or budget memos.

For those agent-generated products, the runbook must not only produce a final document. It must produce an inspectable audit bundle that lets QA answer:

- What data did the agent try to collect?
- Which sources did it use?
- Which claims did it make?
- Which source extracts support each claim?
- Which checks passed, failed, or require human review?
- Should the product be released, regenerated, reviewed, or blocked?

This spec defines the general QA contract for those workflows.

## Design Principles

1. **Runbooks may generate, but QA must verify.** Prompt instructions and AI rules improve generation, but they are not evidence.
2. **Every product run emits structured artifacts.** QA should not depend on reconstructing agent behavior from logs.
3. **Facts, modeled estimates, and advice are different.** Each has different source and routing rules.
4. **Critical claims need source extracts, not just URLs.** A citation ID proves provenance only if the cited text is captured.
5. **Failures should be repairable when possible.** Unsupported sections should produce targeted repair instructions, not only a broad failure.
6. **The contract must generalize.** Meeting briefings, governor orientation briefings, budget memos, and future intel products should share the same QA spine with product-specific schemas.

## Scope

This applies to runbooks that instruct agents to:

- gather external data,
- query databases,
- fetch web pages or PDFs,
- synthesize intelligence,
- generate briefings, memos, reports, recommendations, or outreach artifacts.

It is optional for static reference docs and simple operational procedures, but those can still use the deterministic reference checks.

## Required Run Artifacts

Every QA-enabled runbook run must emit an audit bundle.

Minimum bundle:

```text
output/
  final_artifact.md | final_artifact.json | final_artifact.pdf
  audit_bundle.json
  sources.json
  claims.json
  qa_results.json
```

Recommended bundle:

```text
output/
  final_artifact.*
  audit_bundle.json
  run_manifest.json
  product_spec.json
  required_data_points.json
  sources.json
  source_snapshots/
    source_001.txt
    source_002.html
    source_003.pdf.txt
  claims.json
  claim_citation_pairs.json
  qa_results.json
  repair_plan.json
```

## Audit Bundle

`audit_bundle.json` is the top-level index for QA.

```json
{
  "runbook_version": "runbook-name@commit-or-version",
  "briefing_type": "governor_orientation",
  "product_id": "governor-orientation-nc-2026-05-02",
  "jurisdiction": "North Carolina",
  "official_role": "Governor",
  "run_timestamp": "2026-05-02T20:30:00Z",
  "generator_prompt_version": "governor_orientation_v1",
  "qa_prompt_version": "runbook_qa_v1",
  "final_artifact_path": "output/final_artifact.md",
  "product_spec_path": "output/product_spec.json",
  "required_data_points_path": "output/required_data_points.json",
  "sources_path": "output/sources.json",
  "claims_path": "output/claims.json",
  "qa_results_path": "output/qa_results.json",
  "repair_plan_path": "output/repair_plan.json",
  "final_status": "pass",
  "human_review_notes": []
}
```

## Product Spec

Each generated product type needs a structured definition so QA can evaluate completeness and source requirements.

Example:

```json
{
  "briefing_type": "governor_orientation",
  "required_sections": [
    "executive_summary",
    "role_and_authority",
    "transition_calendar",
    "budget_snapshot",
    "top_agency_decisions",
    "legislative_landscape",
    "public_commitments",
    "first_100_days_recommendations",
    "sources_and_limitations"
  ],
  "required_data_points": [
    {
      "name": "current_state_budget_total",
      "required": true,
      "allowed_source_types": ["official_budget", "audited_financial_report", "official_state_finance_page"],
      "citation_required": true,
      "claim_type": "budget_number",
      "route_if_missing": "regenerate",
      "route_if_unsupported": "block_release"
    },
    {
      "name": "transition_deadline_calendar",
      "required": true,
      "allowed_source_types": ["state_statute", "official_transition_page", "government_record"],
      "citation_required": true,
      "claim_type": "meeting_logistics",
      "route_if_missing": "human_review",
      "route_if_unsupported": "block_release"
    },
    {
      "name": "strategic_recommendations",
      "required": true,
      "allowed_source_types": ["synthesis"],
      "citation_required": false,
      "claim_type": "advice",
      "route_if_missing": "regenerate",
      "route_if_unsupported": "human_review"
    }
  ]
}
```

## Required Data Points

`required_data_points.json` records what the agent attempted to satisfy and what it found.

```json
[
  {
    "name": "current_state_budget_total",
    "required": true,
    "status": "found",
    "value": "$32.1 billion",
    "source_ids": ["source_003"],
    "notes": "Pulled from official enacted budget PDF."
  },
  {
    "name": "incoming_cabinet_confirmation_rules",
    "required": true,
    "status": "not_found",
    "value": null,
    "source_ids": [],
    "notes": "State constitution and transition page checked; no clear confirmation rule found."
  }
]
```

Allowed statuses:

- `found`
- `partial`
- `not_found`
- `not_applicable`
- `blocked`

## Source Registry

Every accessed source must be recorded, whether or not it is cited in the final artifact. QA can then distinguish collected sources from cited sources.

```json
{
  "source_id": "source_003",
  "source_type": "official_budget",
  "title": "FY2026 Enacted State Budget",
  "publisher": "North Carolina Office of State Budget and Management",
  "url": "https://example.gov/budget.pdf",
  "retrieved_at": "2026-05-02T20:10:00Z",
  "retrieval_method": "web_fetch",
  "snapshot_path": "output/source_snapshots/source_003.pdf.txt",
  "content_hash": "sha256:...",
  "access_notes": "",
  "reliability_tier": "primary"
}
```

Required source fields:

- `source_id`
- `source_type`
- `title`
- `url` or `locator`
- `retrieved_at`
- `retrieval_method`
- `snapshot_path` when text or PDF content was used

Recommended fields:

- `publisher`
- `publication_date`
- `content_hash`
- `access_notes`
- `reliability_tier`

## Source Types

Use stable source types so QA can enforce product-specific source rules.

| Source Type | Examples | Default Tier |
| --- | --- | --- |
| `government_record` | agenda, minutes, executive order, agency page | primary |
| `official_budget` | enacted budget, governor budget proposal, finance page | primary |
| `audited_financial_report` | ACFR, audit report | primary |
| `state_statute` | constitution, statute, administrative code | primary |
| `staff_report` | agenda staff report, fiscal note | primary |
| `campaign` | campaign site, platform, filing | primary_or_self_reported |
| `news` | local/state reporting | secondary |
| `academic` | paper, university report | secondary |
| `modeled` | Haystaq, predictive score, internal model output | modeled |
| `database_query` | Databricks, SQL result, internal warehouse | internal |
| `web_search` | search result or uncited lead source | discovery |
| `synthesis` | model reasoning, strategic recommendation | generated |

## Claims

Each factual or material assertion must be represented as a claim.

```json
{
  "claim_id": "claim_001",
  "section_id": "budget_snapshot",
  "claim_text": "The enacted FY2026 state budget totals $32.1 billion.",
  "claim_type": "budget_number",
  "claim_weight": "high",
  "citation_ids": ["source_003"],
  "source_extracts": [
    {
      "source_id": "source_003",
      "extract_id": "extract_001",
      "text": "Total requirements for FY2026 are $32.1 billion...",
      "page": 4,
      "snapshot_path": "output/source_snapshots/source_003.pdf.txt"
    }
  ],
  "required_source_type": "official_budget",
  "route_if_unsupported": "block_release"
}
```

Required claim fields:

- `claim_id`
- `section_id`
- `claim_text`
- `claim_type`
- `claim_weight`
- `citation_ids`
- `source_extracts`
- `required_source_type`
- `route_if_unsupported`

## Claim Types

| Claim Type | Examples | Default Weight | Default Unsupported Route |
| --- | --- | --- | --- |
| `budget_number` | budget total, revenue, deficit, debt | high | block_release |
| `date_or_deadline` | transition date, filing deadline, meeting date | high | block_release |
| `legal_identifier` | statute, bill, executive order, ordinance | high | block_release |
| `named_person_or_role` | agency head, committee chair, staff lead | high | human_review |
| `vote_or_decision_fact` | passed, failed, approved, vetoed | high | block_release |
| `jurisdictional_authority` | what the office can legally do | high | block_release |
| `campaign_commitment` | promise, stated platform, quote | medium | human_review |
| `constituent_priority` | modeled issue priority, polling-like signal | medium | human_review |
| `background_context` | historical framing, issue context | medium | regenerate |
| `news_or_narrative_context` | public controversy, media framing | medium | human_review |
| `modeled_estimate` | predictive score, modeled sentiment | medium | human_review |
| `advice` | recommendation, question to ask, suggested sequencing | low | human_review |

## Citation Syntax

Final artifacts should use predictable inline citation markers:

```markdown
The enacted FY2026 budget totals $32.1 billion [source_003].
```

Citation IDs must match `sources[].source_id`.

For claims supported by multiple sources:

```markdown
The governor appoints agency heads, but several roles require legislative confirmation [source_004][source_005].
```

Do not use citation markers for decorative source lists. Every inline marker should support a nearby factual claim.

## Source Policy Matrix

Each product spec should define a policy matrix. This default matrix can be reused and overridden.

| Data / Claim Type | Acceptable Source Types | Citation Required | Unsupported Route |
| --- | --- | --- | --- |
| Budget totals, fiscal figures | `official_budget`, `audited_financial_report`, `official_state_finance_page` | yes | block_release |
| Legal powers, deadlines, formal authority | `state_statute`, `government_record`, `official_state_page` | yes | block_release |
| Personnel names and roles | `government_record`, `official_state_page`, `campaign` | yes | human_review |
| Vote or formal decision history | `government_record`, `staff_report`, `news` | yes | block_release |
| Campaign promises or public statements | `campaign`, `news`, `government_record` | yes | human_review |
| Public narrative or controversy | `news`, `government_record` | yes | human_review |
| Modeled community priorities | `modeled`, `database_query` | yes | human_review |
| Strategic recommendations | `synthesis`, cited facts beneath recommendation | no for advice, yes for factual premises | human_review |

## QA Checks

QA should run in ordered layers. Earlier layers are deterministic; later layers may use LLM adjudication.

### 1. Schema Validation

Checks:

- `audit_bundle.json` exists and is valid JSON.
- Required artifact files exist.
- `sources.json`, `claims.json`, and `qa_results.json` are valid JSON.
- Product spec includes required sections and data points.

Routes:

- Missing final artifact: `block_release`
- Missing audit bundle: `block_release`
- Missing optional snapshot: `human_review` or `regenerate`, depending on claim weight

### 2. Referential Integrity

Checks:

- Every citation ID in the final artifact exists in `sources.json`.
- Every claim citation ID exists in `sources.json`.
- Every source extract references an existing source.
- Every snapshot path exists when a source is used as evidence.
- Every required data point maps to at least one claim or explicit `not_found` record.
- No unused high-value source is cited only in the source list without a claim.

Routes:

- Missing cited source for high-weight claim: `block_release`
- Missing cited source for medium-weight claim: `regenerate`
- Unused source: annotation only

### 3. Source Reachability And Snapshot Integrity

Checks:

- URLs are syntactically valid.
- Source snapshots exist for evidence-bearing sources.
- Content hashes match when provided.
- Retrieved text is non-empty for PDF/web sources used as evidence.

Routes:

- Snapshot missing for high-weight claim: `human_review`
- URL unavailable but snapshot present: annotation only
- URL unavailable and no snapshot: `regenerate` or `block_release`

### 4. Source Policy

Checks:

- Claim source types are allowed by product spec.
- Critical data points use primary sources when required.
- Modeled data is sourced to `modeled` or `database_query`.
- Advice is not misrepresented as sourced fact.

Routes:

- Disallowed source for high-weight claim: `block_release`
- Disallowed source for medium-weight claim: `human_review`
- Disallowed source for low-weight advice: annotation

### 5. Claim Support

Checks:

- Does the cited extract support the claim?
- Is the claim a fair paraphrase?
- Is it overclaiming beyond the extract?
- Does it contradict the extract?

Preferred implementation:

- Deterministic checks first for exact numbers, dates, names, and legal IDs.
- LLM adjudication second for semantic support.

Meeting-briefing QA is the model here: build an evidence bundle per claim, then ask a triage judge to classify support. Escalate only high-weight not-OK claims.

Suggested support categories:

- `supported`
- `directionally_supported`
- `reasonable_inference`
- `modeled`
- `unsupported`
- `contradicted`
- `unverifiable`

Routes:

- High-weight `unsupported` or `contradicted`: `block_release`
- Medium-weight `unsupported`: `human_review` or targeted `regenerate`
- Low-weight `unsupported`: annotation or `human_review`

### 6. Numeric, Date, And Name Copy Checks

Checks:

- Dollar amounts match source extracts.
- Percentages and calculated changes are arithmetically valid.
- Dates are copied correctly.
- Named people and roles match cited source text.
- Legal identifiers are exact.

Routes:

- Incorrect number/date/legal ID in high-weight claim: `block_release`
- Ambiguous but plausible number/date: `human_review`

### 7. Modeled Data Labeling

Checks:

- Modeled estimates are labeled as modeled, not surveyed or measured.
- Model source appears in `sources.json`.
- Model limitations appear in the final artifact when modeled data influences recommendations.

Routes:

- Unlabeled modeled data in user-facing artifact: `human_review`
- Modeled data presented as measured fact: `block_release`

### 8. Required Data Completeness

Checks:

- Every required data point is `found`, `partial`, `not_found`, or `not_applicable`.
- Missing required data points have notes explaining search attempts.
- Final artifact does not silently omit critical sections.

Routes:

- Missing required high-risk data without explanation: `regenerate`
- Missing required section: `regenerate`
- Missing but explicitly unavailable: `human_review` or pass with limitation, depending on product spec

## Gating Policy

QA returns one final status.

```json
{
  "status": "pass",
  "reasons": [],
  "failed_checks": [],
  "repair_plan": []
}
```

Statuses:

| Status | Meaning |
| --- | --- |
| `pass` | Safe to release. Only non-blocking annotations remain. |
| `regenerate` | Product can likely be fixed automatically by regenerating targeted sections. |
| `human_review` | Product may be useful but needs a person to resolve ambiguity or risk. |
| `block_release` | Do not release. Clear unsupported or incorrect material claim. |

Routing priority:

1. Any absolute failure -> `block_release`
2. Any high-weight unsupported claim that may be repairable -> `regenerate`
3. Any unresolved medium-risk support issue -> `human_review`
4. Only annotations -> `pass`

## Targeted Repair

When possible, QA should produce repair instructions.

```json
{
  "failed_section": "budget_snapshot",
  "failure_type": "unsupported_budget_number",
  "failed_claim_ids": ["claim_001"],
  "repair_instruction": "Regenerate only the budget snapshot using official budget or audited financial sources.",
  "allowed_source_types": ["official_budget", "audited_financial_report"],
  "attempt_number": 1,
  "max_attempts": 2
}
```

Recommended policy:

- Allow up to 2 targeted regeneration attempts for `regenerate`.
- Do not regenerate the whole artifact if only one section failed.
- Preserve passing sections and their claims unless their dependencies changed.
- After max attempts, route to `human_review` or `block_release`.

## QA Results

`qa_results.json` should include one result per check and one final decision.

```json
{
  "briefing_id": "governor-orientation-nc-2026-05-02",
  "status": "human_review",
  "checks": [
    {
      "check_id": "ref_integrity_001",
      "check_type": "referential_integrity",
      "status": "pass",
      "severity": "info",
      "message": "All inline citations resolve to sources."
    },
    {
      "check_id": "claim_support_004",
      "check_type": "claim_support",
      "status": "fail",
      "severity": "high",
      "claim_id": "claim_001",
      "message": "Budget total is not supported by cited extract.",
      "recommended_route": "block_release"
    }
  ],
  "final_decision": {
    "status": "human_review",
    "reasons": ["One high-weight claim failed support review but may be repairable."],
    "failed_checks": ["claim_support_004"]
  }
}
```

## Relationship To AI Rules

AI rules should define how agents write and cite:

- use `sources.json`,
- use `[source_id]` inline citations,
- capture source snapshots,
- emit claims,
- do not fabricate data,
- label modeled data.

Runbook QA verifies whether the agent actually complied. AI rules are an authoring contract; QA is the enforcement layer.

## Relationship To Meeting Briefing QA

Meeting-briefing QA provides the right verification pattern:

```text
input -> grounding -> extraction -> evidence bundles -> adjudication -> routing -> reporting
```

Runbook QA generalizes this pattern:

```text
audit bundle -> source registry -> claims -> evidence bundles -> deterministic checks -> optional LLM adjudication -> routing -> repair plan
```

The difference is that runbook QA starts from a general product spec and audit bundle instead of a fixed meeting briefing schema.

## Governor Orientation Briefing Application

For governor orientation briefings, high-risk claims include:

- constitutional powers,
- appointment and confirmation authority,
- budget totals and fiscal constraints,
- legal deadlines,
- agency names and leadership,
- stated campaign commitments,
- recent legislative decisions,
- major public controversies.

Required sections should likely include:

- executive summary,
- role and legal authority,
- transition calendar,
- budget and fiscal snapshot,
- agency and cabinet map,
- legislative landscape,
- public commitments and constraints,
- first 100 days recommendations,
- source limitations.

Recommended release rule:

- Budget, legal authority, deadlines, and named-role claims must be supported by primary sources or blocked.
- Public narrative claims may use reputable news but should route to human review if unsupported.
- Strategic recommendations may be synthesized, but their factual premises must be cited.

## Minimum Viable Implementation

Build in this order:

1. Require `sources.json`, `claims.json`, and `audit_bundle.json`.
2. Validate citation IDs and source IDs.
3. Validate required sections and required data points.
4. Require source extracts for high-weight claims.
5. Add deterministic checks for exact numbers, dates, names, and legal IDs.
6. Add LLM support adjudication for high-weight claims only.
7. Add targeted repair instructions.

This gives immediate referential integrity without making every runbook pay the full cost of semantic QA.
