We are building a QA layer for runbook-generated governance briefings.

## Context

You are given:

1. Follow all implementation details defined in `groundedness_implementation_spec.md` → canonical implementation spec (primary source of truth)
2. Do not restate or reinterpret those rules unless necessary for compatibility with `qa_spec.md`. → engineer’s existing spec (must remain compatible)
 
### Compatibility Rule

- Do NOT remove or rename existing fields from `qa_spec.md`
- You MAY add new fields (e.g. `risk`, `verification_category`, `normalized_claim_type`)
- Extend rather than replace
- If there is a conflict:
  - preserve engineer schema
  - implement as additive
  - flag the conflict for human review

Prefer backward compatibility over schema elegance.

---

## Implementation Priorities

Build in this order:

1. Referential integrity (claims ↔ sources ↔ citations)
2. Required data completeness
3. Claim support verification
4. Risk classification + gating
5. Targeted regeneration

---

## QA Pipeline Requirements

Implement ordered checks:

1. schema validation
2. referential integrity
3. source reachability / snapshot integrity
4. source policy validation
5. claim support classification
6. numeric/date/name copy checks
7. modeled data labeling
8. required data completeness

Use final statuses:
`pass | regenerate | human_review | block_release`

---

## Output Requirements

The system must emit:

- final artifact
- audit bundle
- sources
- claims
- claim_citation_pairs
- qa_results
- repair_plan (when needed)
- audit log fields

---


## Claim Model Requirements

- Preserve domain-specific `claim_type` (e.g. `budget_number`, `date_or_deadline`)
- Add:
  - `normalized_claim_type` → `factual | modeled | inferred | recommendation | calculation`
  - `risk` → `low | medium | high`
  - `verification_category` → support classification

---

## Maintainability Requirements

Build as a modular pipeline, not a monolith.

Core rules:
- Use a pipeline orchestrator with independent QA checks
- Each check has one responsibility and returns a structured result
- Only the gating engine determines final status
- Product-specific rules must be config-driven (not hardcoded)
- Deterministic checks run before LLM-based checks
- LLM verification (if used) must be replaceable

Each QA check returns:

{
  "check_id": "...",
  "check_type": "...",
  "status": "pass | fail | warning",
  "severity": "info | low | medium | high",
  "claim_id": null,
  "source_id": null,
  "message": "...",
  "recommended_route": "pass | regenerate | human_review | block_release",
  "recommended_fix": "..."
}

---

## MVP Scope

Minimum modules:

- schema validation
- citation/source integrity
- source policy validation
- required data completeness
- modeled data labeling
- risk classification
- gating
- repair planning

---
## MVP Implementation Decisions

The QA layer should be implemented as a fresh Python package under `runbook_trustlayer/`, with both a CLI and importable Python API.

The CLI validates a generated `output/` folder. The Python API should expose the same validation pipeline for future integration into briefing generation workflows.

MVP behavior:
- Do not perform live network checks by default.
- Validate URL/locator syntax, snapshot presence, text presence, and content hashes when available.
- Live reachability checks may be added behind an optional flag.
- Claim support verification should be deterministic-first.
- LLM verification should be represented by a replaceable adapter interface, but not required for MVP.
- Ship a generic/default policy config first, with optional initial support for `governor_orientation`.

Artifact severity:
- Missing core artifacts should block release.
- Missing recommended artifacts should warn or regenerate depending on whether QA can still evaluate the artifact.
- Block only when QA cannot safely evaluate release.
- Regenerate when missing structure is likely fixable automatically.
- Warn when equivalent information exists elsewhere.

## Final Rule

If simplicity conflicts with extensibility, prefer extensibility — as long as the MVP still supports:

- citation integrity
- required data completeness
- risk classification
- gating decisions
- repair planning