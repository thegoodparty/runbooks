"""Numeric, date, name, and legal identifier copy checks."""

import re
from typing import Dict, Iterable, List

from .base import QACheck, ResultFactory
from .claim_support import DATE_RE, LEGAL_RE, NUMBER_RE, ClaimSupportCheck
from ..artifacts import ArtifactContext
from ..models import QAResult


NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b")


class NumericDateNameCopyCheck(QACheck):
    check_type = "copy_check"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        support = ClaimSupportCheck()
        for claim in context.claims:
            evidence = "\n".join(support._evidence_texts(context, claim))
            if not evidence.strip():
                continue
            missing = list(self._missing_exact_tokens(claim, evidence))
            if missing:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "high" if claim.get("claim_weight") == "high" else "medium",
                        f"Claim {claim.get('claim_id')} has exact-copy tokens absent from cited evidence.",
                        claim_id=str(claim.get("claim_id")),
                        recommended_route=self._route_for_claim(claim),
                        recommended_fix="Correct copied numbers, dates, names, or legal identifiers from the cited source.",
                        missing_tokens=missing,
                    )
                )
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "No numeric, date, name, or legal identifier copy mismatches were found.",
                )
            )
        return results

    def _missing_exact_tokens(self, claim: Dict[str, object], evidence: str) -> Iterable[str]:
        claim_text = str(claim.get("claim_text", ""))
        tokens = []
        for regex in (NUMBER_RE, DATE_RE, LEGAL_RE):
            tokens.extend(match.strip() for match in regex.findall(claim_text) if match.strip())
        if claim.get("claim_type") == "named_person_or_role":
            tokens.extend(match.strip() for match in NAME_RE.findall(claim_text) if match.strip())
        evidence_lower = evidence.lower()
        for token in sorted(set(tokens)):
            if token.lower() not in evidence_lower:
                yield token

    def _route_for_claim(self, claim: Dict[str, object]) -> str:
        if claim.get("claim_weight") == "high":
            return "block_release"
        if claim.get("claim_weight") == "medium":
            return "human_review"
        return "human_review"

