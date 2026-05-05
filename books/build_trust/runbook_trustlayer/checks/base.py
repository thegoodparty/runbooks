"""Base classes and helpers for QA checks."""

from typing import List, Optional

from ..artifacts import ArtifactContext
from ..models import QAResult


class QACheck:
    check_type = "base"

    def run(self, context: ArtifactContext, factory: "ResultFactory") -> List[QAResult]:
        raise NotImplementedError


class ResultFactory:
    def __init__(self) -> None:
        self._counters = {}

    def make(
        self,
        check_type: str,
        status: str,
        severity: str,
        message: str,
        claim_id: Optional[str] = None,
        source_id: Optional[str] = None,
        recommended_route: str = "pass",
        recommended_fix: str = "",
        **metadata: object,
    ) -> QAResult:
        count = self._counters.get(check_type, 0) + 1
        self._counters[check_type] = count
        return QAResult(
            check_id=f"{check_type}_{count:03d}",
            check_type=check_type,
            status=status,
            severity=severity,
            claim_id=claim_id,
            source_id=source_id,
            message=message,
            recommended_route=recommended_route,
            recommended_fix=recommended_fix,
            metadata={key: value for key, value in metadata.items() if value is not None},
        )

