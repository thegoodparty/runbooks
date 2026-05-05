"""Orchestrator and importable API for runbook QA."""

from pathlib import Path
from typing import Iterable, Optional
import json

from .artifacts import load_context
from .checks import DEFAULT_CHECKS
from .checks.base import ResultFactory
from .checks.claim_support import ClaimSupportCheck
from .config import load_config
from .gating import gate_results
from .models import ValidationReport
from .repair import build_repair_plan


class RunbookQAPipeline:
    def __init__(
        self,
        config_name: Optional[str] = None,
        live_checks: bool = False,
        llm_verifier: object = None,
        checks: Optional[Iterable[object]] = None,
    ) -> None:
        self.config_name = config_name
        self.live_checks = live_checks
        self.llm_verifier = llm_verifier
        if checks is None:
            checks = [
                check if not isinstance(check, ClaimSupportCheck) else ClaimSupportCheck(llm_verifier)
                for check in DEFAULT_CHECKS
            ]
        self.checks = list(checks)

    def validate(self, output_dir: Path) -> ValidationReport:
        output_dir = Path(output_dir)
        bootstrap_context = load_context(output_dir, load_config(self.config_name), live_checks=self.live_checks)
        config = load_config(self.config_name, bootstrap_context.product_spec, bootstrap_context.audit_bundle)
        context = load_context(output_dir, config, live_checks=self.live_checks)
        factory = ResultFactory()
        results = []
        for check in self.checks:
            results.extend(check.run(context, factory))
        decision = gate_results(results)
        repair_plan = build_repair_plan(context, results) if decision.status != "pass" else []
        audit_log = self._audit_log(context, decision.status, results)
        return ValidationReport(
            output_dir=output_dir,
            checks=results,
            final_decision=decision,
            repair_plan=repair_plan,
            audit_log=audit_log,
            enriched_claims=context.claims,
        )

    def _audit_log(self, context, final_status: str, results):
        audit = dict(context.audit_bundle)
        audit.setdefault("sources_used", [source.get("source_id") for source in context.sources if source.get("source_id")])
        audit.setdefault("claims", [claim.get("claim_id") for claim in context.claims if claim.get("claim_id")])
        audit["qa_results"] = [result.to_dict() for result in results]
        audit["final_status"] = final_status
        audit.setdefault("human_review_notes", [])
        return audit

    def write_outputs(
        self,
        report: ValidationReport,
        write_enriched_claims: bool = False,
    ) -> None:
        output_dir = report.output_dir
        (output_dir / "qa_results.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        repair_path = output_dir / "repair_plan.json"
        if report.repair_plan:
            repair_path.write_text(
                json.dumps([item.to_dict() for item in report.repair_plan], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        elif repair_path.exists():
            repair_path.write_text("[]\n", encoding="utf-8")
        if write_enriched_claims:
            (output_dir / "claims.json").write_text(
                json.dumps(report.enriched_claims, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


def validate_output_folder(
    output_dir: Path,
    config_name: Optional[str] = None,
    live_checks: bool = False,
    llm_verifier: object = None,
) -> ValidationReport:
    return RunbookQAPipeline(
        config_name=config_name,
        live_checks=live_checks,
        llm_verifier=llm_verifier,
    ).validate(Path(output_dir))
