"""Modeled data labeling checks."""

from typing import List

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..models import QAResult


class ModeledDataLabelingCheck(QACheck):
    check_type = "modeled_data_labeling"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        source_by_id = context.source_by_id
        for claim in context.claims:
            is_modeled = claim.get("normalized_claim_type") == "modeled" or claim.get("claim_type") in {
                "modeled_estimate",
                "constituent_priority",
            }
            if not is_modeled:
                continue
            claim_id = str(claim.get("claim_id"))
            claim_text = str(claim.get("claim_text", ""))
            lowered = claim_text.lower()
            citation_ids = [str(item) for item in claim.get("citation_ids", [])]
            model_sources = [
                source_by_id[source_id]
                for source_id in citation_ids
                if source_id in source_by_id
                and source_by_id[source_id].get("source_type") in {"modeled", "database_query"}
            ]
            if not model_sources:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Modeled claim {claim_id} lacks a modeled or database_query source.",
                        claim_id=claim_id,
                        recommended_route="human_review",
                        recommended_fix="Cite the model output or database query that produced the modeled estimate.",
                    )
                )
            if not any(term in lowered for term in ("model", "modeled", "estimate", "estimated", "score", "predictive")):
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Modeled claim {claim_id} is not labeled as modeled or estimated.",
                        claim_id=claim_id,
                        recommended_route="human_review",
                        recommended_fix="Label modeled estimates clearly in claim text and final artifact.",
                    )
                )
            if any(term in lowered for term in ("surveyed", "measured fact", "observed fact")):
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Modeled claim {claim_id} may be presented as measured fact.",
                        claim_id=claim_id,
                        recommended_route="block_release",
                        recommended_fix="Rewrite modeled data as an estimate and include model limitations.",
                    )
                )
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "Modeled estimates are labeled and sourced when present.",
                )
            )
        return results

