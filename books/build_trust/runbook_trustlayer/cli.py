"""Command line interface for validating a runbook output folder."""

import argparse
import json
import sys
from pathlib import Path

from .models import ROUTE_PRIORITY
from .pipeline import RunbookQAPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate runbook QA artifacts in an output folder.")
    parser.add_argument("output_dir", type=Path, help="Folder containing final_artifact.*, audit_bundle.json, sources.json, and claims.json.")
    parser.add_argument("--config", dest="config_name", default=None, help="Built-in config name, e.g. default or governor_orientation.")
    parser.add_argument("--live-checks", action="store_true", help="Opt in to live URL reachability checks.")
    parser.add_argument("--no-write", action="store_true", help="Do not write qa_results.json or repair_plan.json.")
    parser.add_argument("--write-enriched-claims", action="store_true", help="Overwrite claims.json with additive QA fields.")
    parser.add_argument("--json", action="store_true", help="Print the full QA report as JSON.")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pipeline = RunbookQAPipeline(config_name=args.config_name, live_checks=args.live_checks)
    report = pipeline.validate(args.output_dir)
    if not args.no_write:
        pipeline.write_outputs(report, write_enriched_claims=args.write_enriched_claims)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"status: {report.status}")
        print(f"checks: {len(report.checks)}")
        if report.final_decision.reasons:
            print("reasons:")
            for reason in report.final_decision.reasons[:10]:
                print(f"- {reason}")
            if len(report.final_decision.reasons) > 10:
                print(f"- ... {len(report.final_decision.reasons) - 10} more")
    return exit_code(report.status)


def exit_code(status: str) -> int:
    if status == "pass":
        return 0
    if status in {"regenerate", "human_review"}:
        return 1
    if status == "block_release":
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())

