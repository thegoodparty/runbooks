"""Source URL, snapshot, and hash integrity checks."""

from hashlib import sha256
from typing import Dict, Iterable, List, Set
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .base import QACheck, ResultFactory
from ..artifacts import ArtifactContext
from ..config import max_weight
from ..models import QAResult


class SourceIntegrityCheck(QACheck):
    check_type = "source_integrity"

    def run(self, context: ArtifactContext, factory: ResultFactory) -> List[QAResult]:
        results: List[QAResult] = []
        evidence_sources = self._evidence_sources(context)
        weights_by_source = self._weights_by_source(context)
        for source in context.sources:
            source_id = str(source.get("source_id", ""))
            if not source_id:
                continue
            self._check_locator(source, factory, results)
            if source_id in evidence_sources:
                self._check_snapshot_or_text(context, source, weights_by_source.get(source_id, "medium"), factory, results)
            self._check_hash(context, source, factory, results)
            if context.live_checks and source.get("url"):
                self._check_live_url(source, factory, results)
        if not results:
            results.append(
                factory.make(
                    self.check_type,
                    "pass",
                    "info",
                    "Source locators, snapshots, and hashes passed deterministic integrity checks.",
                )
            )
        return results

    def _evidence_sources(self, context: ArtifactContext) -> Set[str]:
        return {
            str(citation_id)
            for claim in context.claims
            for citation_id in claim.get("citation_ids", [])
            if citation_id
        }

    def _weights_by_source(self, context: ArtifactContext) -> Dict[str, str]:
        weights: Dict[str, List[str]] = {}
        for claim in context.claims:
            for citation_id in claim.get("citation_ids", []):
                weights.setdefault(str(citation_id), []).append(str(claim.get("claim_weight", "medium")))
        return {source_id: max_weight(source_weights) for source_id, source_weights in weights.items()}

    def _check_locator(self, source: Dict[str, object], factory: ResultFactory, results: List[QAResult]) -> None:
        source_id = str(source.get("source_id", ""))
        url = str(source.get("url", "") or "")
        locator = str(source.get("locator", "") or "")
        if url:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https", "file"} or not parsed.path and not parsed.netloc:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Source {source_id} has an invalid URL.",
                        source_id=source_id,
                        recommended_route="regenerate",
                        recommended_fix="Replace the URL with a syntactically valid http(s), file, or locator value.",
                    )
                )
        elif not locator:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "medium",
                    f"Source {source_id} has neither URL nor locator.",
                    source_id=source_id,
                    recommended_route="regenerate",
                    recommended_fix="Add a URL or stable internal locator for the source.",
                )
            )

    def _check_snapshot_or_text(
        self,
        context: ArtifactContext,
        source: Dict[str, object],
        weight: str,
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        source_id = str(source.get("source_id", ""))
        snapshot_path = context.resolve_path(source.get("snapshot_path"))
        retrieved_text = str(source.get("retrieved_text_or_snapshot", "") or "")
        if snapshot_path and snapshot_path.exists():
            try:
                if snapshot_path.stat().st_size == 0:
                    results.append(
                        factory.make(
                            self.check_type,
                            "fail",
                            "high" if weight == "high" else "medium",
                            f"Source {source_id} snapshot exists but is empty.",
                            source_id=source_id,
                            recommended_route="human_review" if weight == "high" else "regenerate",
                            recommended_fix="Capture non-empty retrieved text for evidence-bearing sources.",
                        )
                    )
            except OSError:
                results.append(
                    factory.make(
                        self.check_type,
                        "fail",
                        "medium",
                        f"Source {source_id} snapshot could not be inspected.",
                        source_id=source_id,
                        recommended_route="regenerate",
                        recommended_fix="Regenerate the source snapshot.",
                    )
                )
            return
        if retrieved_text.strip():
            return
        results.append(
            factory.make(
                self.check_type,
                "fail",
                "high" if weight == "high" else "medium",
                f"Source {source_id} lacks a usable snapshot or retrieved text.",
                source_id=source_id,
                recommended_route="human_review" if weight == "high" else "regenerate",
                recommended_fix="Capture snapshot_path or retrieved_text_or_snapshot for cited evidence.",
            )
        )

    def _check_hash(
        self,
        context: ArtifactContext,
        source: Dict[str, object],
        factory: ResultFactory,
        results: List[QAResult],
    ) -> None:
        content_hash = str(source.get("content_hash", "") or "")
        if not content_hash:
            return
        if not content_hash.startswith("sha256:"):
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    f"Source {source.get('source_id')} uses unsupported content_hash format.",
                    source_id=str(source.get("source_id")),
                    recommended_route="pass",
                    recommended_fix="Use sha256:<hex-digest> for deterministic hash validation.",
                )
            )
            return
        expected = content_hash.split(":", 1)[1]
        content = self._hashable_content(context, source)
        if content is None:
            return
        actual = sha256(content).hexdigest()
        if actual != expected:
            results.append(
                factory.make(
                    self.check_type,
                    "fail",
                    "high",
                    f"Source {source.get('source_id')} content_hash does not match captured content.",
                    source_id=str(source.get("source_id")),
                    recommended_route="block_release",
                    recommended_fix="Regenerate the source snapshot or update content_hash after verifying provenance.",
                )
            )

    def _hashable_content(self, context: ArtifactContext, source: Dict[str, object]) -> bytes:
        snapshot_path = context.resolve_path(source.get("snapshot_path"))
        if snapshot_path and snapshot_path.exists():
            try:
                return snapshot_path.read_bytes()
            except OSError:
                return None
        text = source.get("retrieved_text_or_snapshot")
        if isinstance(text, str) and text:
            return text.encode("utf-8")
        return None

    def _check_live_url(self, source: Dict[str, object], factory: ResultFactory, results: List[QAResult]) -> None:
        url = str(source.get("url", "") or "")
        if not url.startswith(("http://", "https://")):
            return
        try:
            request = Request(url, method="HEAD", headers={"User-Agent": "runbook-trustlayer/0"})
            with urlopen(request, timeout=5) as response:  # noqa: S310 - opt-in live QA check.
                if response.status >= 400:
                    raise OSError(f"HTTP {response.status}")
        except Exception as exc:  # noqa: BLE001 - live reachability is best-effort QA metadata.
            results.append(
                factory.make(
                    self.check_type,
                    "warning",
                    "low",
                    f"Live reachability check failed for source {source.get('source_id')}: {exc}",
                    source_id=str(source.get("source_id")),
                    recommended_route="pass",
                    recommended_fix="Confirm the URL manually or rely on the captured snapshot.",
                )
            )

