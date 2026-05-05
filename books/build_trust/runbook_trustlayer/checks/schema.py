"""Schema and artifact presence validation."""

from typing import Any, Dict, List

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..models import QAResult


class SchemaValidationCheck(QACheck):
    check_type = "schema_validation"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        self._check_core_artifacts(context, factory, results)
        self._check_recommended_artifacts(context, factory, results)
        self._check_audit_fields(context, factory, results)
        self._check_sources(context, factory, results)
        self._check_claims(context, factory, results)
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "Core artifacts are present and parseable.",
                )
            )
        return results

    def _check_core_artifacts(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        for name in ("audit_bundle.json", "sources.json", "claims.json", "qa_results.json"):
            loaded = context.loaded_json[name]
            if not loaded.exists:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Missing required core artifact: {name}.",
                        recommended_route="block_release",
                        recommended_fix=f"Emit {name} before release validation.",
                    )
                )
            elif loaded.error:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"{name} is not valid JSON: {loaded.error}",
                        recommended_route="block_release",
                        recommended_fix=f"Regenerate {name} as schema-valid JSON.",
                    )
                )
        if context.final_artifact_path is None:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "high",
                    "Missing required final artifact.",
                    recommended_route="block_release",
                    recommended_fix="Emit final_artifact.* or set audit_bundle.final_artifact_path.",
                )
            )
        elif not context.final_artifact_path.exists():
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "high",
                    f"Missing required final artifact at referenced path: {context.final_artifact_path}",
                    recommended_route="block_release",
                    recommended_fix="Emit the final artifact at the path referenced by audit_bundle.json.",
                )
            )

    def _check_recommended_artifacts(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        product_spec_loaded = context.loaded_json["product_spec.json"]
        if not product_spec_loaded.exists:
            route = "regenerate" if context.config.requires_explicit_product_spec else "pass"
            status = "fail" if route == "regenerate" else "warning"
            results.append(
                factory.make(
                    self.check_type,
                    status,
                    "medium" if route == "regenerate" else "low",
                    "Missing recommended product_spec.json; using configured defaults.",
                    recommended_route=route,
                    recommended_fix="Emit product_spec.json when briefing-specific required sections or data points are needed.",
                )
            )
        elif product_spec_loaded.error:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "medium",
                    f"product_spec.json is not valid JSON: {product_spec_loaded.error}",
                    recommended_route="regenerate",
                    recommended_fix="Regenerate product_spec.json as valid JSON.",
                )
            )

        pairs_loaded = context.loaded_json["claim_citation_pairs.json"]
        if not pairs_loaded.exists:
            has_linkage = all(isinstance(claim.get("citation_ids"), list) for claim in context.claims)
            results.append(
                factory.make(
                    self.check_type,
                    "warning" if has_linkage else "fail",
                    "low" if has_linkage else "medium",
                    "Missing recommended claim_citation_pairs.json.",
                    recommended_route="pass" if has_linkage else "regenerate",
                    recommended_fix=(
                        "Equivalent citation linkage exists in claims.json."
                        if has_linkage
                        else "Emit claim_citation_pairs.json or add citation_ids to each claim."
                    ),
                )
            )
        elif pairs_loaded.error:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "medium",
                    f"claim_citation_pairs.json is not valid JSON: {pairs_loaded.error}",
                    recommended_route="regenerate",
                    recommended_fix="Regenerate claim_citation_pairs.json as valid JSON.",
                )
            )

        required_loaded = context.loaded_json["required_data_points.json"]
        declared_required_points = bool(context.config.required_data_points)
        if not required_loaded.exists and declared_required_points:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "medium",
                    "Missing required_data_points.json while product spec declares required data points.",
                    recommended_route="regenerate",
                    recommended_fix="Emit required_data_points.json with found/partial/not_found/not_applicable/blocked statuses.",
                )
            )
        elif not required_loaded.exists:
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    "Missing recommended required_data_points.json.",
                    recommended_route="pass",
                    recommended_fix="Emit required_data_points.json for stronger completeness QA.",
                )
            )
        elif required_loaded.error:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "medium",
                    f"required_data_points.json is not valid JSON: {required_loaded.error}",
                    recommended_route="regenerate",
                    recommended_fix="Regenerate required_data_points.json as valid JSON.",
                )
            )

    def _check_audit_fields(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        if not context.audit_bundle:
            return
        recommended = (
            "runbook_version",
            "briefing_type",
            "jurisdiction",
            "official_role",
            "run_timestamp",
            "generator_prompt_version",
            "qa_prompt_version",
            "final_status",
            "human_review_notes",
        )
        missing = [field for field in recommended if field not in context.audit_bundle]
        if missing:
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    "Audit bundle is missing recommended audit log fields.",
                    recommended_route="pass",
                    recommended_fix="Add missing audit log fields for later inspectability.",
                    missing_fields=missing,
                )
            )

    def _check_sources(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        if not context.loaded_json["sources.json"].exists or context.loaded_json["sources.json"].error:
            return
        if not isinstance(context.loaded_json["sources.json"].data, (list, dict)):
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "high",
                    "sources.json must be a list or an object containing sources.",
                    recommended_route="block_release",
                    recommended_fix="Emit sources.json as an array or {\"sources\": [...]}.",
                )
            )
            return
        for index, source in enumerate(context.sources):
            source_id = source.get("source_id")
            if not source_id:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Source at index {index} is missing source_id.",
                        recommended_route="block_release",
                        recommended_fix="Add stable source_id values before citations can be verified.",
                    )
                )
                continue
            missing = self._missing_source_fields(source)
            if missing:
                route = "regenerate" if "source_type" in missing else "pass"
                results.append(
                    factory.make(
                        self.check_type,
                        "fail" if route == "regenerate" else "warning",
                        "medium" if route == "regenerate" else "low",
                        f"Source {source_id} is missing metadata fields.",
                        source_id=str(source_id),
                        recommended_route=route,
                        recommended_fix="Add required source metadata without renaming existing fields.",
                        missing_fields=missing,
                    )
                )

    def _missing_source_fields(self, source: Dict[str, Any]) -> List[str]:
        missing = []
        for field in ("source_type", "title", "retrieved_at", "retrieval_method"):
            if not source.get(field):
                missing.append(field)
        if not source.get("url") and not source.get("locator"):
            missing.append("url_or_locator")
        return missing

    def _check_claims(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        if not context.loaded_json["claims.json"].exists or context.loaded_json["claims.json"].error:
            return
        if not isinstance(context.loaded_json["claims.json"].data, (list, dict)):
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "high",
                    "claims.json must be a list or an object containing claims.",
                    recommended_route="block_release",
                    recommended_fix="Emit claims.json as an array or {\"claims\": [...]}.",
                )
            )
            return
        additive_missing = False
        for index, claim in enumerate(context.claims):
            claim_id = claim.get("claim_id")
            if not claim_id:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Claim at index {index} is missing claim_id.",
                        recommended_route="block_release",
                        recommended_fix="Add stable claim_id values before claim QA can run.",
                    )
                )
                continue
            missing = [
                field
                for field in (
                    "section_id",
                    "claim_text",
                    "claim_type",
                    "citation_ids",
                    "required_source_type",
                    "route_if_unsupported",
                )
                if field not in claim
            ]
            if missing:
                route = "block_release" if {"claim_text", "claim_type", "citation_ids"} & set(missing) else "regenerate"
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high" if route == "block_release" else "medium",
                        f"Claim {claim_id} is missing required fields.",
                        claim_id=str(claim_id),
                        recommended_route=route,
                        recommended_fix="Add missing claim fields while preserving existing claim_type values.",
                        missing_fields=missing,
                    )
                )
            for field in ("normalized_claim_type", "risk", "verification_category"):
                raw_claim = self._raw_claim(context, claim_id)
                if raw_claim is not None and field not in raw_claim:
                    additive_missing = True
        if additive_missing:
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    "Some claims are missing additive groundedness fields; QA enriched them in memory.",
                    recommended_route="pass",
                    recommended_fix="Emit normalized_claim_type, risk, and verification_category in future claims.json files.",
                )
            )

    def _raw_claim(self, context: ArtifactContext, claim_id: Any) -> Dict[str, Any]:
        raw = context.loaded_json["claims.json"].data
        if isinstance(raw, dict):
            raw_claims = raw.get("claims", [])
        else:
            raw_claims = raw
        for claim in raw_claims if isinstance(raw_claims, list) else []:
            if isinstance(claim, dict) and claim.get("claim_id") == claim_id:
                return claim
        return {}
