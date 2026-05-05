"""Deterministic-first claim support classification."""

import re
from typing import Dict, Iterable, List, Optional, Set

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext, read_text
from ..models import QAResult


TOKEN_RE = re.compile(r"[A-Za-z0-9$%.,/-]+")
NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|trillion|%|percent))?", re.I)
DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b",
    re.I,
)
LEGAL_RE = re.compile(r"\b(?:HB|SB|H\.R\.|S\.|§|Section)\s?[\w.-]+\b", re.I)


class ClaimSupportCheck(QACheck):
    check_type = "claim_support"

    def __init__(self, llm_verifier: object = None) -> None:
        self.llm_verifier = llm_verifier

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        for claim in context.claims:
            category = self._classify_claim(context, claim)
            claim["verification_category"] = category
            if category in {"supported", "directionally_supported", "reasonable_inference", "modeled"}:
                results.append(
                    factory.make(
                        self.check_type,
                        "pass" if category == "supported" else "warning",
                        "info" if category == "supported" else "low",
                        f"Claim {claim.get('claim_id')} classified as {category}.",
                        claim_id=str(claim.get("claim_id")),
                        recommended_route="pass",
                    )
                )
            else:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        self._severity_for_claim(claim),
                        f"Claim {claim.get('claim_id')} classified as {category}.",
                        claim_id=str(claim.get("claim_id")),
                        recommended_route=self._route_for_category(claim, category),
                        recommended_fix="Regenerate the claim from cited extracts or route it for human review.",
                        verification_category=category,
                    )
                )
        if not results:
            results.append(factory.make(self.check_type, "pass", "info", "No claims were present to classify."))
        return results

    def _classify_claim(self, context: ArtifactContext, claim: Dict[str, object]) -> str:
        if claim.get("normalized_claim_type") == "modeled":
            return "modeled"
        evidence_texts = self._evidence_texts(context, claim)
        evidence = "\n".join(evidence_texts)
        if not evidence.strip():
            return "unverifiable"
        claim_text = str(claim.get("claim_text", ""))
        important_tokens = set(self._important_tokens(claim_text))
        if important_tokens and not all(token.lower() in evidence.lower() for token in important_tokens):
            return "unsupported"
        overlap = self._word_overlap(claim_text, evidence)
        if overlap >= 0.65:
            return "supported"
        if overlap >= 0.35:
            return "directionally_supported"
        llm_category = self._llm_classify(claim, evidence_texts)
        if llm_category:
            return llm_category
        return "unverifiable"

    def _evidence_texts(self, context: ArtifactContext, claim: Dict[str, object]) -> List[str]:
        texts: List[str] = []
        extracts = claim.get("source_extracts", claim.get("source_extract", []))
        if isinstance(extracts, list):
            for extract in extracts:
                if isinstance(extract, dict):
                    text = extract.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
                    snapshot_path = context.resolve_path(extract.get("snapshot_path"))
                    if snapshot_path and snapshot_path.exists():
                        snapshot_text = read_text(snapshot_path)
                        if snapshot_text.strip():
                            texts.append(snapshot_text)
                elif isinstance(extract, str) and extract.strip():
                    texts.append(extract)
        for citation_id in claim.get("citation_ids", []):
            source = context.source_by_id.get(str(citation_id))
            if not source:
                continue
            text = source.get("retrieved_text_or_snapshot")
            if isinstance(text, str) and text.strip():
                texts.append(text)
            snapshot_path = context.resolve_path(source.get("snapshot_path"))
            if snapshot_path and snapshot_path.exists():
                snapshot_text = read_text(snapshot_path)
                if snapshot_text.strip():
                    texts.append(snapshot_text)
        return texts

    def _important_tokens(self, text: str) -> Iterable[str]:
        for regex in (NUMBER_RE, DATE_RE, LEGAL_RE):
            for match in regex.findall(text):
                token = match.strip()
                if token:
                    yield token

    def _word_overlap(self, claim_text: str, evidence: str) -> float:
        claim_words = self._content_words(claim_text)
        evidence_words = self._content_words(evidence)
        if not claim_words:
            return 1.0
        return len(claim_words & evidence_words) / len(claim_words)

    def _content_words(self, text: str) -> Set[str]:
        stopwords = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "by",
            "for",
            "from",
            "in",
            "is",
            "of",
            "on",
            "or",
            "the",
            "to",
            "with",
        }
        words = {
            token.lower().strip(".,")
            for token in TOKEN_RE.findall(text)
            if len(token.strip(".,").lower()) > 2
        }
        return {word for word in words if word not in stopwords}

    def _llm_classify(self, claim: Dict[str, object], evidence_texts: List[str]) -> Optional[str]:
        verifier = self.llm_verifier
        if verifier is None or not hasattr(verifier, "classify"):
            return None
        category = verifier.classify(claim, evidence_texts)
        allowed = {
            "supported",
            "directionally_supported",
            "reasonable_inference",
            "modeled",
            "unsupported",
            "contradicted",
            "unverifiable",
        }
        return category if category in allowed else None

    def _route_for_category(self, claim: Dict[str, object], category: str) -> str:
        if category == "contradicted":
            return "block_release"
        weight = claim.get("claim_weight")
        if weight == "high":
            return str(claim.get("route_if_unsupported", "block_release"))
        if weight == "medium":
            return "human_review"
        return "human_review"

    def _severity_for_claim(self, claim: Dict[str, object]) -> str:
        return "high" if claim.get("claim_weight") == "high" else "medium"

