"""
Validate a completed output/ folder against the QA protocol.

Usage:
    uv run qa_validate.py --output-dir output/

Checks (in order):
  1. Schema — required files exist and are valid JSON
  2. Referential integrity — inline citations resolve to sources; claim citation_ids resolve
  3. Snapshot integrity — snapshot_path exists for every evidence-bearing source
  4. Source coverage — every high-weight claim has at least one source extract
  5. Required data completeness — sources and claims lists are non-empty

Writes qa_results.json and repair_plan.json (when needed) into output-dir.
Exits 0 on pass, 1 on any non-pass status.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


GATING_PRIORITY = ["block_release", "regenerate", "human_review", "pass"]

HIGH_WEIGHT_TYPES = {
    "budget_number",
    "date_or_deadline",
    "legal_identifier",
    "named_person_or_role",
    "vote_or_decision_fact",
    "jurisdictional_authority",
}


@dataclass
class Check:
    check_id: str
    check_type: str
    status: str  # pass | fail | warning
    severity: str  # info | low | medium | high
    message: str
    recommended_route: str = "pass"
    recommended_fix: str = ""
    claim_id: str | None = None
    source_id: str | None = None


@dataclass
class ValidationResult:
    checks: list[Check] = field(default_factory=list)
    repair_plan: list[dict] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    def final_status(self) -> str:
        routes = [c.recommended_route for c in self.checks if c.status != "pass"]
        if not routes:
            return "pass"
        for status in GATING_PRIORITY:
            if status in routes:
                return status
        return "pass"


def load_json(path: Path) -> tuple[Any, str | None]:
    if not path.exists():
        return None, f"{path} not found"
    try:
        return json.loads(path.read_text()), None
    except json.JSONDecodeError as e:
        return None, f"{path} is invalid JSON: {e}"


def check_schema(output_dir: Path, result: ValidationResult) -> tuple[dict, list, list]:
    """Check 1: required files exist and parse."""
    required = ["audit_bundle.json", "sources.json", "claims.json"]
    audit_bundle, sources, claims = {}, [], []

    for filename in required:
        data, err = load_json(output_dir / filename)
        if err:
            result.add(Check(
                check_id=f"schema_{filename.replace('.', '_')}",
                check_type="schema",
                status="fail",
                severity="high",
                message=err,
                recommended_route="block_release",
                recommended_fix=f"Create and populate {filename} per the QA protocol.",
            ))
        else:
            result.add(Check(
                check_id=f"schema_{filename.replace('.', '_')}",
                check_type="schema",
                status="pass",
                severity="info",
                message=f"{filename} exists and is valid JSON.",
            ))
            if filename == "audit_bundle.json":
                audit_bundle = data
            elif filename == "sources.json":
                sources = data if isinstance(data, list) else []
            elif filename == "claims.json":
                claims = data if isinstance(data, list) else []

    final_path = output_dir / "final_artifact.md"
    if not final_path.exists():
        # Try common extensions
        candidates = list(output_dir.glob("final_artifact.*"))
        if not candidates:
            result.add(Check(
                check_id="schema_final_artifact",
                check_type="schema",
                status="fail",
                severity="high",
                message="No final_artifact.* found in output/.",
                recommended_route="block_release",
                recommended_fix="Generate and save the final artifact before running QA.",
            ))
        else:
            result.add(Check(
                check_id="schema_final_artifact",
                check_type="schema",
                status="pass",
                severity="info",
                message=f"Final artifact found: {candidates[0].name}",
            ))

    return audit_bundle, sources, claims


def check_referential_integrity(output_dir: Path, sources: list, claims: list, result: ValidationResult) -> None:
    """Check 2: citation IDs in claims resolve to sources; inline markers in artifact resolve."""
    source_ids = {s.get("source_id") for s in sources if s.get("source_id")}

    for claim in claims:
        cid = claim.get("claim_id", "unknown")
        for sid in claim.get("citation_ids", []):
            if sid not in source_ids:
                weight = claim.get("claim_weight", "medium")
                route = "block_release" if weight == "high" else "regenerate"
                result.add(Check(
                    check_id=f"ref_integrity_{cid}_{sid}",
                    check_type="referential_integrity",
                    status="fail",
                    severity="high" if weight == "high" else "medium",
                    message=f"Claim {cid} cites {sid} which does not exist in sources.json.",
                    recommended_route=route,
                    recommended_fix=f"Add source {sid} to sources.json or correct the citation in claim {cid}.",
                    claim_id=cid,
                    source_id=sid,
                ))

    artifact_candidates = list(output_dir.glob("final_artifact.*"))
    if artifact_candidates:
        text = artifact_candidates[0].read_text()
        inline_ids = set(re.findall(r'\[([a-zA-Z0-9_]+)\]', text))
        for sid in inline_ids:
            if sid not in source_ids:
                result.add(Check(
                    check_id=f"ref_integrity_inline_{sid}",
                    check_type="referential_integrity",
                    status="fail",
                    severity="medium",
                    message=f"Inline citation [{sid}] in final artifact does not resolve to any source.",
                    recommended_route="human_review",
                    recommended_fix=f"Add source {sid} to sources.json or remove the inline marker.",
                    source_id=sid,
                ))

    if claims:
        result.add(Check(
            check_id="ref_integrity_summary",
            check_type="referential_integrity",
            status="pass",
            severity="info",
            message="Referential integrity check complete.",
        ))


def check_snapshot_integrity(sources: list, result: ValidationResult) -> None:
    """Check 3: snapshot_path exists for evidence-bearing sources."""
    for source in sources:
        sid = source.get("source_id", "unknown")
        snapshot = source.get("snapshot_path")
        if snapshot:
            path = Path(snapshot)
            if not path.exists():
                result.add(Check(
                    check_id=f"snapshot_{sid}",
                    check_type="snapshot_integrity",
                    status="fail",
                    severity="medium",
                    message=f"Source {sid} declares snapshot_path {snapshot} but file does not exist.",
                    recommended_route="human_review",
                    recommended_fix=f"Capture and save the source content to {snapshot}.",
                    source_id=sid,
                ))


def check_source_coverage(claims: list, result: ValidationResult) -> None:
    """Check 4: high-weight claims have at least one source extract."""
    for claim in claims:
        cid = claim.get("claim_id", "unknown")
        weight = claim.get("claim_weight", "medium")
        ctype = claim.get("claim_type", "")
        extracts = claim.get("source_extracts", [])

        if weight == "high" or ctype in HIGH_WEIGHT_TYPES:
            if not extracts:
                result.add(Check(
                    check_id=f"coverage_{cid}",
                    check_type="source_coverage",
                    status="fail",
                    severity="high",
                    message=f"High-weight claim {cid} ({ctype!r}) has no source extracts.",
                    recommended_route="block_release",
                    recommended_fix=f"Add a source extract to claim {cid} from a supporting source.",
                    claim_id=cid,
                ))


def check_completeness(sources: list, claims: list, result: ValidationResult) -> None:
    """Check 5: sources and claims are non-empty."""
    if not sources:
        result.add(Check(
            check_id="completeness_sources",
            check_type="required_data_completeness",
            status="fail",
            severity="high",
            message="sources.json is empty. No sources were recorded for this run.",
            recommended_route="regenerate",
            recommended_fix="Populate sources.json with every source accessed during generation.",
        ))
    if not claims:
        result.add(Check(
            check_id="completeness_claims",
            check_type="required_data_completeness",
            status="fail",
            severity="high",
            message="claims.json is empty. No claims were recorded for this run.",
            recommended_route="regenerate",
            recommended_fix="Populate claims.json with every factual assertion in the final artifact.",
        ))


def build_repair_plan(result: ValidationResult) -> list[dict]:
    failed = [c for c in result.checks if c.status == "fail" and c.recommended_fix]
    return [
        {
            "check_id": c.check_id,
            "check_type": c.check_type,
            "recommended_route": c.recommended_route,
            "repair_instruction": c.recommended_fix,
            "claim_id": c.claim_id,
            "source_id": c.source_id,
        }
        for c in failed
    ]


def write_results(output_dir: Path, result: ValidationResult, audit_bundle: dict) -> None:
    status = result.final_status()
    failed_checks = [c.check_id for c in result.checks if c.status == "fail"]
    reasons = [c.message for c in result.checks if c.status == "fail"]

    qa_results = {
        "product_id": audit_bundle.get("product_id", ""),
        "status": status,
        "checks": [
            {
                "check_id": c.check_id,
                "check_type": c.check_type,
                "status": c.status,
                "severity": c.severity,
                "message": c.message,
                "recommended_route": c.recommended_route,
                "claim_id": c.claim_id,
                "source_id": c.source_id,
            }
            for c in result.checks
        ],
        "final_decision": {
            "status": status,
            "reasons": reasons,
            "failed_checks": failed_checks,
        },
    }

    (output_dir / "qa_results.json").write_text(json.dumps(qa_results, indent=2))

    repair_plan = build_repair_plan(result)
    if repair_plan:
        (output_dir / "repair_plan.json").write_text(json.dumps(repair_plan, indent=2))

    audit_bundle["final_status"] = status
    (output_dir / "audit_bundle.json").write_text(json.dumps(audit_bundle, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", default="output", help="Output directory to validate (default: output/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    result = ValidationResult()

    audit_bundle, sources, claims = check_schema(output_dir, result)
    check_referential_integrity(output_dir, sources, claims, result)
    check_snapshot_integrity(sources, result)
    check_source_coverage(claims, result)
    check_completeness(sources, claims, result)

    write_results(output_dir, result, audit_bundle)

    status = result.final_status()
    fail_count = sum(1 for c in result.checks if c.status == "fail")
    warn_count = sum(1 for c in result.checks if c.status == "warning")

    print(f"\nStatus: {status.upper()}")
    print(f"Checks: {len(result.checks)} total, {fail_count} failed, {warn_count} warnings")
    if fail_count:
        print("\nFailed checks:")
        for c in result.checks:
            if c.status == "fail":
                print(f"  [{c.severity}] {c.check_id}: {c.message}")
        print(f"\nSee {output_dir}/repair_plan.json for fix instructions.")

    sys.exit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
