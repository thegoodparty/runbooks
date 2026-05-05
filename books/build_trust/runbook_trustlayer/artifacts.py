"""Artifact loading and normalization for runbook QA."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

from .config import ProductConfig, enrich_claim


CORE_JSON = ("audit_bundle.json", "sources.json", "claims.json", "qa_results.json")


@dataclass
class LoadedJson:
    path: Path
    exists: bool
    data: Any = None
    error: Optional[str] = None


@dataclass
class ArtifactContext:
    output_dir: Path
    config: ProductConfig
    live_checks: bool = False
    audit_bundle: Dict[str, Any] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    claims: List[Dict[str, Any]] = field(default_factory=list)
    claim_citation_pairs: List[Dict[str, Any]] = field(default_factory=list)
    required_data_points: List[Dict[str, Any]] = field(default_factory=list)
    product_spec: Optional[Dict[str, Any]] = None
    existing_qa_results: Any = None
    final_artifact_path: Optional[Path] = None
    final_artifact_text: str = ""
    loaded_json: Dict[str, LoadedJson] = field(default_factory=dict)

    @property
    def source_by_id(self) -> Dict[str, Dict[str, Any]]:
        return {str(source.get("source_id")): source for source in self.sources if source.get("source_id")}

    @property
    def claim_by_id(self) -> Dict[str, Dict[str, Any]]:
        return {str(claim.get("claim_id")): claim for claim in self.claims if claim.get("claim_id")}

    def resolve_path(self, value: Optional[str]) -> Optional[Path]:
        if not value:
            return None
        candidate = Path(value)
        if candidate.is_absolute():
            return candidate
        direct = self.output_dir / candidate
        if direct.exists():
            return direct
        parts = candidate.parts
        if parts and parts[0] in {self.output_dir.name, "output"}:
            return self.output_dir.joinpath(*parts[1:])
        return direct


def read_json(path: Path) -> LoadedJson:
    if not path.exists():
        return LoadedJson(path=path, exists=False)
    try:
        return LoadedJson(path=path, exists=True, data=json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001 - preserve parse reason for QA output.
        return LoadedJson(path=path, exists=True, error=str(exc))


def list_from_payload(payload: Any, key: str) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        value = payload.get(key, [])
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def dict_from_payload(payload: Any) -> Dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def find_final_artifact(output_dir: Path, audit_bundle: Dict[str, Any]) -> Tuple[Optional[Path], str]:
    candidate = audit_bundle.get("final_artifact_path")
    if candidate:
        path = resolve_output_path(output_dir, candidate)
        if path.exists():
            return path, read_text(path)
        return path, ""
    for path in sorted(output_dir.glob("final_artifact.*")):
        if path.is_file():
            return path, read_text(path)
    return None, ""


def resolve_output_path(output_dir: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    direct = output_dir / candidate
    if direct.exists():
        return direct
    parts = candidate.parts
    if parts and parts[0] in {output_dir.name, "output"}:
        return output_dir.joinpath(*parts[1:])
    return direct


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_context(output_dir: Path, config: ProductConfig, live_checks: bool = False) -> ArtifactContext:
    output_dir = Path(output_dir)
    loaded = {name: read_json(output_dir / name) for name in CORE_JSON}
    optional_names = ("product_spec.json", "required_data_points.json", "claim_citation_pairs.json")
    loaded.update({name: read_json(output_dir / name) for name in optional_names})

    audit_bundle = dict_from_payload(loaded["audit_bundle.json"].data)
    product_spec = dict_from_payload(loaded["product_spec.json"].data) or None
    sources = list_from_payload(loaded["sources.json"].data, "sources")
    claims = [enrich_claim(claim) for claim in list_from_payload(loaded["claims.json"].data, "claims")]

    required_data_points = list_from_payload(loaded["required_data_points.json"].data, "required_data_points")
    if not required_data_points and isinstance(audit_bundle.get("required_data_points"), list):
        required_data_points = [item for item in audit_bundle["required_data_points"] if isinstance(item, dict)]

    claim_citation_pairs = list_from_payload(
        loaded["claim_citation_pairs.json"].data,
        "claim_citation_pairs",
    )
    if not claim_citation_pairs and isinstance(audit_bundle.get("claim_citation_pairs"), list):
        claim_citation_pairs = [item for item in audit_bundle["claim_citation_pairs"] if isinstance(item, dict)]

    final_path, final_text = find_final_artifact(output_dir, audit_bundle)
    return ArtifactContext(
        output_dir=output_dir,
        config=config,
        live_checks=live_checks,
        audit_bundle=audit_bundle,
        sources=sources,
        claims=claims,
        claim_citation_pairs=claim_citation_pairs,
        required_data_points=required_data_points,
        product_spec=product_spec,
        existing_qa_results=loaded["qa_results.json"].data,
        final_artifact_path=final_path,
        final_artifact_text=final_text,
        loaded_json=loaded,
    )

