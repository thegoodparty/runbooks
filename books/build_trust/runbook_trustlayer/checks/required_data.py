"""Required data point and section completeness checks."""

from typing import Dict, List, Set

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..models import QAResult


ALLOWED_DATA_STATUSES = {"found", "partial", "not_found", "not_applicable", "blocked"}


class RequiredDataCompletenessCheck(QACheck):
    check_type = "required_data_completeness"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        self._check_required_sections(context, factory, results)
        self._check_required_data_points(context, factory, results)
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "Required sections and data points are complete or explicitly accounted for.",
                )
            )
        return results

    def _check_required_sections(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        text = context.final_artifact_text.lower().replace("-", "_")
        for section in context.config.required_sections:
            normalized = section.lower().replace(" ", "_").replace("-", "_")
            human = normalized.replace("_", " ")
            if normalized not in text and human not in text.replace("_", " "):
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Final artifact is missing required section {section}.",
                        recommended_route="regenerate",
                        recommended_fix=f"Regenerate or add the missing {section} section.",
                        missing_section=section,
                    )
                )

    def _check_required_data_points(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        required_spec = {
            point.get("name"): point
            for point in context.config.required_data_points
            if point.get("name") and point.get("required", True)
        }
        recorded = {point.get("name"): point for point in context.required_data_points if point.get("name")}
        for name, spec in required_spec.items():
            if name not in recorded:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Required data point {name} is missing from required_data_points.json.",
                        recommended_route="regenerate",
                        recommended_fix="Emit required data point records for every required product-spec item.",
                        data_point=name,
                    )
                )
        for point in context.required_data_points:
            name = str(point.get("name", ""))
            status = point.get("status")
            if status not in ALLOWED_DATA_STATUSES:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Required data point {name} has invalid status {status}.",
                        recommended_route="regenerate",
                        recommended_fix="Use found, partial, not_found, not_applicable, or blocked.",
                        data_point=name,
                    )
                )
                continue
            if point.get("required", True) and status == "not_found" and not point.get("notes"):
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Required data point {name} is not_found without search notes.",
                        recommended_route="regenerate",
                        recommended_fix="Add notes explaining search attempts or regenerate the missing data.",
                        data_point=name,
                    )
                )
            elif point.get("required", True) and status == "blocked":
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Required data point {name} is blocked.",
                        recommended_route="human_review",
                        recommended_fix="Route blocked data point to a human or provide an explicit limitation.",
                        data_point=name,
                    )
                )
            elif point.get("required", True) and status in {"found", "partial"}:
                self._check_data_point_mapping(context, point, factory, results)

    def _check_data_point_mapping(
        self,
        context: ArtifactContext,
        point: Dict[str, object],
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        name = str(point.get("name", ""))
        source_ids = {str(source_id) for source_id in point.get("source_ids", []) if source_id}
        matching_claims = [
            claim
            for claim in context.claims
            if claim.get("data_point") == name
            or claim.get("data_point_name") == name
            or claim.get("required_data_point") == name
            or source_ids.intersection(str(item) for item in claim.get("citation_ids", []))
        ]
        if not matching_claims:
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    f"Required data point {name} is found but not clearly mapped to a claim.",
                    recommended_route="pass",
                    recommended_fix="Attach data_point or source_ids mappings to related claims for auditability.",
                    data_point=name,
                )
            )

