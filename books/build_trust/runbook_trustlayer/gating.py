"""Final status routing for QA results."""

from typing import Iterable, List

from .models import FinalDecision, QAResult, ROUTE_PRIORITY


def gate_results(results: Iterable[QAResult]) -> FinalDecision:
    status = "pass"
    reasons: List[str] = []
    failed_checks: List[str] = []
    for result in results:
        route = result.recommended_route if result.recommended_route in ROUTE_PRIORITY else "pass"
        if ROUTE_PRIORITY[route] > ROUTE_PRIORITY[status]:
            status = route
        if result.status == "fail" or route != "pass":
            failed_checks.append(result.check_id)
            reasons.append(result.message)
    return FinalDecision(status=status, reasons=reasons, failed_checks=failed_checks)

