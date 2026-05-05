"""Targeted repair plan generation."""

from typing import Dict, Iterable, List

from .artifacts import ArtifactContext
from .models import QAResult, RepairInstruction


def build_repair_plan(context: ArtifactContext, results: Iterable[QAResult]) -> List[RepairInstruction]:
    claim_by_id = context.claim_by_id
    attempt = int(context.audit_bundle.get("repair_attempt_number", context.audit_bundle.get("attempt_number", 1)) or 1)
    plan: List[RepairInstruction] = []
    seen = set()
    for result in results:
        if result.recommended_route == "pass":
            continue
        claim = claim_by_id.get(str(result.claim_id)) if result.claim_id else None
        section = str((claim or {}).get("section_id") or _section_for_result(result))
        key = (section, result.check_type, result.claim_id, result.source_id)
        if key in seen:
            continue
        seen.add(key)
        allowed = []
        if claim:
            policy = context.config.policy_for_claim(claim)
            allowed = list(policy.get("allowed_source_types", []))
        plan.append(
            RepairInstruction(
                failed_section=section,
                failure_type=result.check_type,
                failed_claim_ids=[str(result.claim_id)] if result.claim_id else [],
                repair_instruction=result.recommended_fix or _default_instruction(result),
                allowed_source_types=allowed,
                attempt_number=attempt,
                max_attempts=2,
            )
        )
    return plan


def _section_for_result(result: QAResult) -> str:
    if result.check_type == "schema_validation":
        return "artifact_bundle"
    if result.source_id:
        return "sources"
    return "global"


def _default_instruction(result: QAResult) -> str:
    if result.claim_id:
        return f"Regenerate or review claim {result.claim_id} for {result.check_type}."
    return f"Regenerate or review the artifact bundle for {result.check_type}."

