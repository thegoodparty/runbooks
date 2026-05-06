"""
Scaffold output/ with stub artifact files before a generation run.

Usage:
    uv run qa_init.py --product-id <id> --briefing-type <type> [--output-dir output/]

Creates output/ (or the specified directory) with empty stubs for:
  audit_bundle.json, sources.json, claims.json, qa_results.json, source_snapshots/

Safe to re-run: existing files are NOT overwritten, so partial runs are not reset.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_FILES = ["audit_bundle.json", "sources.json", "claims.json", "qa_results.json"]


def scaffold(product_id: str, briefing_type: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "source_snapshots").mkdir(exist_ok=True)

    audit_bundle_path = output_dir / "audit_bundle.json"
    if not audit_bundle_path.exists():
        audit_bundle = {
            "product_id": product_id,
            "briefing_type": briefing_type,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "generator": "",
            "final_artifact_path": str(output_dir / "final_artifact.md"),
            "sources_path": str(output_dir / "sources.json"),
            "claims_path": str(output_dir / "claims.json"),
            "qa_results_path": str(output_dir / "qa_results.json"),
            "final_status": None,
        }
        audit_bundle_path.write_text(json.dumps(audit_bundle, indent=2))
        print(f"created {audit_bundle_path}")
    else:
        print(f"exists  {audit_bundle_path} (not overwritten)")

    for stub_file, stub_content in [
        ("sources.json", []),
        ("claims.json", []),
        ("qa_results.json", {"status": None, "checks": [], "final_decision": None}),
    ]:
        path = output_dir / stub_file
        if not path.exists():
            path.write_text(json.dumps(stub_content, indent=2))
            print(f"created {path}")
        else:
            print(f"exists  {path} (not overwritten)")

    print(f"\nReady. Populate output artifacts during generation, then run:")
    print(f"  uv run qa_validate.py --output-dir {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--product-id", required=True, help="Unique ID for this run (e.g. briefing-nc-gov-2026-05-05)")
    parser.add_argument("--briefing-type", required=True, help="Product type (e.g. governor_orientation, meeting_briefing)")
    parser.add_argument("--output-dir", default="output", help="Output directory to scaffold (default: output/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    scaffold(args.product_id, args.briefing_type, output_dir)


if __name__ == "__main__":
    main()
