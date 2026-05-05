"""Shared data models for the runbook QA pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


FINAL_STATUSES = ("pass", "regenerate", "human_review", "block_release")
RESULT_STATUSES = ("pass", "fail", "warning")
SEVERITIES = ("info", "low", "medium", "high")

ROUTE_PRIORITY = {
    "pass": 0,
    "human_review": 1,
    "regenerate": 2,
    "block_release": 3,
}


@dataclass
class QAResult:
    check_id: str
    check_type: str
    status: str
    severity: str
    message: str
    claim_id: Optional[str] = None
    source_id: Optional[str] = None
    recommended_route: str = "pass"
    recommended_fix: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "check_id": self.check_id,
            "check_type": self.check_type,
            "status": self.status,
            "severity": self.severity,
            "claim_id": self.claim_id,
            "source_id": self.source_id,
            "message": self.message,
            "recommended_route": self.recommended_route,
            "recommended_fix": self.recommended_fix,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class FinalDecision:
    status: str
    reasons: List[str]
    failed_checks: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reasons": self.reasons,
            "failed_checks": self.failed_checks,
        }


@dataclass
class RepairInstruction:
    failed_section: str
    failure_type: str
    failed_claim_ids: List[str]
    repair_instruction: str
    allowed_source_types: List[str] = field(default_factory=list)
    attempt_number: int = 1
    max_attempts: int = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failed_section": self.failed_section,
            "failure_type": self.failure_type,
            "failed_claim_ids": self.failed_claim_ids,
            "repair_instruction": self.repair_instruction,
            "allowed_source_types": self.allowed_source_types,
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
        }


@dataclass
class ValidationReport:
    output_dir: Path
    checks: List[QAResult]
    final_decision: FinalDecision
    repair_plan: List[RepairInstruction]
    audit_log: Dict[str, Any]
    enriched_claims: List[Dict[str, Any]]

    @property
    def status(self) -> str:
        return self.final_decision.status

    def to_dict(self) -> Dict[str, Any]:
        briefing_id = (
            self.audit_log.get("briefing_id")
            or self.audit_log.get("product_id")
            or self.audit_log.get("briefing_type")
            or "unknown"
        )
        return {
            "briefing_id": briefing_id,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "final_decision": self.final_decision.to_dict(),
            "repair_plan": [item.to_dict() for item in self.repair_plan],
            "audit_log": self.audit_log,
        }

