"""Citation, source, and claim referential integrity checks."""

import re
from typing import Dict, List, Set

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..models import QAResult


CITATION_RE = re.compile(r"\[([A-Za-z0-9_.:-]+)\]")


class ReferentialIntegrityCheck(QACheck):
    check_type = "referential_integrity"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        source_ids = set(context.source_by_id)
        self._check_final_artifact_citations(context, factory, results, source_ids)
        self._check_claim_citations(context, factory, results, source_ids)
        self._check_source_extracts(context, factory, results, source_ids)
        self._check_cited_sources_have_claims(context, factory, results)
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "All inline citations, claim citations, and source extracts resolve.",
                )
            )
        return results

    def _check_final_artifact_citations(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
        source_ids: Set[str],
    ) -> None:
        cited_ids = self._artifact_citation_ids(context.final_artifact_text, source_ids)
        for citation_id in sorted(cited_ids):
            if citation_id not in source_ids:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Final artifact cites unknown source ID {citation_id}.",
                        source_id=citation_id,
                        recommended_route="block_release",
                        recommended_fix="Add the cited source to sources.json or remove the unsupported citation.",
                    )
                )

    def _artifact_citation_ids(self, text: str, source_ids: Set[str]) -> Set[str]:
        cited = set()
        for token in CITATION_RE.findall(text or ""):
            if token in source_ids or token.startswith("source_"):
                cited.add(token)
        return cited

    def _check_claim_citations(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
        source_ids: Set[str],
    ) -> None:
        for claim in context.claims:
            claim_id = str(claim.get("claim_id", ""))
            citation_ids = claim.get("citation_ids", [])
            if not isinstance(citation_ids, list):
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"Claim {claim_id} citation_ids must be a list.",
                        claim_id=claim_id,
                        recommended_route="block_release",
                        recommended_fix="Emit citation_ids as an array of source IDs.",
                    )
                )
                continue
            if not citation_ids and claim.get("claim_type") != "advice":
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        self._severity_for_claim(claim),
                        f"Claim {claim_id} has no citations.",
                        claim_id=claim_id,
                        recommended_route=self._route_for_claim(claim, default="regenerate"),
                        recommended_fix="Add citations to evidence-bearing claims or recast as uncited advice.",
                    )
                )
            for citation_id in citation_ids:
                if citation_id not in source_ids:
                    results.append(
                        factory.make(
                            self.check_type,
                            "fail",
                            self._severity_for_claim(claim),
                            f"Claim {claim_id} cites unknown source ID {citation_id}.",
                            claim_id=claim_id,
                            source_id=str(citation_id),
                            recommended_route=self._route_for_claim(claim, default="regenerate"),
                            recommended_fix="Add the source to sources.json or update the claim citation.",
                        )
                    )

    def _check_source_extracts(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
        source_ids: Set[str],
    ) -> None:
        for claim in context.claims:
            claim_id = str(claim.get("claim_id", ""))
            extracts = claim.get("source_extracts", claim.get("source_extract", []))
            if not extracts and claim.get("claim_weight") == "high":
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high",
                        f"High-weight claim {claim_id} is missing source extracts.",
                        claim_id=claim_id,
                        recommended_route="human_review",
                        recommended_fix="Capture source extracts supporting the claim before release.",
                    )
                )
                continue
            if isinstance(extracts, list):
                for extract in extracts:
                    if isinstance(extract, dict):
                        source_id = extract.get("source_id")
                        if source_id and source_id not in source_ids:
                            results.append(
                                factory.make(
                                    self.check_type,
                                    "fail",
                                    self._severity_for_claim(claim),
                                    f"Claim {claim_id} source extract references unknown source ID {source_id}.",
                                    claim_id=claim_id,
                                    source_id=str(source_id),
                                    recommended_route=self._route_for_claim(claim, default="regenerate"),
                                    recommended_fix="Attach the extract to an existing source_id.",
                                )
                            )
                    elif isinstance(extract, str):
                        results.append(
                            factory.make(
                                self.check_type,
                                "warning",
                                "low",
                                f"Claim {claim_id} uses legacy string source_extract entries.",
                                claim_id=claim_id,
                                recommended_route="pass",
                                recommended_fix="Prefer structured source_extracts with source_id and snapshot_path.",
                            )
                        )

    def _check_cited_sources_have_claims(
        self,
        context: ArtifactContext,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        artifact_citations = self._artifact_citation_ids(context.final_artifact_text, set(context.source_by_id))
        claim_citations = {
            str(citation_id)
            for claim in context.claims
            for citation_id in claim.get("citation_ids", [])
            if citation_id
        }
        for source_id in sorted(artifact_citations - claim_citations):
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    f"Source {source_id} appears in final artifact citations but is not attached to a claim.",
                    source_id=source_id,
                    recommended_route="pass",
                    recommended_fix="Attach decorative or orphan citations to nearby claims, or move them to a source list.",
                )
            )

    def _route_for_claim(self, claim: Dict[str, object], default: str) -> str:
        if claim.get("claim_weight") == "high":
            return str(claim.get("route_if_unsupported", "block_release"))
        if claim.get("claim_weight") == "medium":
            return default
        return "human_review"

    def _severity_for_claim(self, claim: Dict[str, object]) -> str:
        return "high" if claim.get("claim_weight") == "high" else "medium"

