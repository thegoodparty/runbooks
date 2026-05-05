"""Product-specific source policy validation."""

from typing import Dict, List

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..models import QAResult


class SourcePolicyCheck(QACheck):
    check_type = "source_policy"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        source_by_id = context.source_by_id
        for claim in context.claims:
            policy = context.config.policy_for_claim(claim)
            citation_ids = claim.get("citation_ids", [])
            if policy.get("citation_required") and not citation_ids:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        self._severity_for_claim(claim),
                        f"Claim {claim.get('claim_id')} requires a citation under source policy.",
                        claim_id=str(claim.get("claim_id")),
                        recommended_route=self._route_for_claim(claim, policy),
                        recommended_fix="Add allowed citations or update product policy if the claim is uncited advice.",
                    )
                )
                continue
            allowed = set(policy.get("allowed_source_types", []))
            if not allowed:
                continue
            for citation_id in citation_ids:
                source = source_by_id.get(str(citation_id))
                if not source:
                    continue
                source_type = source.get("source_type")
                if source_type not in allowed:
                    route = self._disallowed_route(claim)
                    results.append(
                        factory.make(
                            self.check_type,
                            "fail" if route != "pass" else "warning",
                            self._severity_for_claim(claim) if route != "pass" else "low",
                            f"Claim {claim.get('claim_id')} cites disallowed source type {source_type}.",
                            claim_id=str(claim.get("claim_id")),
                            source_id=str(citation_id),
                            recommended_route=route,
                            recommended_fix="Use an allowed source type for this claim or update product policy.",
                            allowed_source_types=sorted(allowed),
                            actual_source_type=source_type,
                        )
                    )
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "All claim citations comply with configured source policies.",
                )
            )
        return results

    def _route_for_claim(self, claim: Dict[str, object], policy: Dict[str, object]) -> str:
        return str(policy.get("route_if_unsupported") or claim.get("route_if_unsupported") or "human_review")

    def _disallowed_route(self, claim: Dict[str, object]) -> str:
        weight = claim.get("claim_weight")
        if weight == "high":
            return str(claim.get("route_if_unsupported", "block_release"))
        if weight == "medium":
            return "human_review"
        return "pass"

    def _severity_for_claim(self, claim: Dict[str, object]) -> str:
        return "high" if claim.get("claim_weight") == "high" else "medium"

