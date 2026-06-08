"""Layer 2 — INTEGRATION tests for whole-artifact release_verdict routing.

A small, separate layer that covers whole-artifact verdict routing: given a fixture
with a known route-mix, does compute_release_verdict resolve to the expected verdict?
This complements the per-check unit layer (test_qa_spine_unit_checks.py), which asserts
individual check results and ignores the verdict.

Verdict logic under test (qa_validate.compute_release_verdict):
  - route=block   + status fail            -> block
  - route=annotate+ status fail/warning    -> warn
  - route=diagnostic                        -> never drives the verdict

Fixtures (each a thin, single-condition derivation of the clean baseline):
  - agent_assembled_baseline.json            clean             -> ok
  - variants/variant_single_blocking_defect  one block defect  -> block
  - variants/variant_single_annotate_defect  one annotate defect -> warn
  - variants/variant_identity_missing        whole-doc identity -> block
  - variants/variant_schema_drift            whole-doc schema   -> warn

Every verdict below was calibrated by ACTUALLY RUNNING the validator offline
(`qa_validate.py <artifact> --no-llm --no-check-urls`), never hand-guessed.
"""
from __future__ import annotations

import qa_validate

from conftest import PACKET_DIR, run_offline_checks  # shared fixtures live in conftest.py


def _checks(spec: dict, artifact_rel: str) -> list:
    """Load + run the deterministic spine offline (URL liveness off) for a variant."""
    return run_offline_checks(spec, PACKET_DIR / artifact_rel)


def _verdict(spec: dict, artifact_rel: str) -> str:
    """Mirror `qa_validate.py <artifact> --no-llm --no-check-urls`: deterministic checks
    only, URL liveness off, then compute the release verdict."""
    return qa_validate.compute_release_verdict(_checks(spec, artifact_rel), traces=[])


def _driver_present(checks: list, check_id: str, *, route: str) -> bool:
    """True if some emission of check_id is a fail/warning routed via `route` — i.e. a
    finding that can actually DRIVE the verdict (diagnostics never do)."""
    return any(
        c.check_id == check_id and c.route == route and c.status in ("fail", "warning")
        for c in checks
    )


def test_clean_baseline_routes_ok(spec):
    """The clean baseline resolves to ok; its only non-pass findings are diagnostics
    (source_hierarchy policy gap + faithful-paraphrase coherence), which never drive
    the verdict."""
    assert _verdict(spec, "agent_assembled_baseline.json") == "ok"


def test_single_blocking_defect_routes_block(spec):
    """One block-routed defect (claim_008 extract absent from its cited source) →
    block, DRIVEN by extracts_appear_in_cited_source routing block — not some other
    block-routed check tripping for the wrong reason."""
    checks = _checks(spec, "variants/variant_single_blocking_defect.json")
    assert qa_validate.compute_release_verdict(checks, traces=[]) == "block"
    assert _driver_present(checks, "extracts_appear_in_cited_source", route="block")


def test_single_annotate_defect_routes_warn(spec):
    """One annotate-routed defect (advocacy 'Push for' in an authored summary) → warn,
    DRIVEN by prohibited_phrases routing annotate."""
    checks = _checks(spec, "variants/variant_single_annotate_defect.json")
    assert qa_validate.compute_release_verdict(checks, traces=[]) == "warn"
    assert _driver_present(checks, "prohibited_phrases", route="annotate")


def test_identity_missing_routes_block(spec):
    """A whole-doc identity failure (official_name blanked) → block. This variant trips
    BOTH identity_fields_present (route=block) AND schema_validation (route=annotate);
    the block wins. We assert the block is DRIVEN by identity_fields_present, and confirm
    the concurrent annotate-routed schema_validation finding is also present (so the test
    catches the verdict resolving to block for the wrong reason)."""
    checks = _checks(spec, "variants/variant_identity_missing.json")
    assert qa_validate.compute_release_verdict(checks, traces=[]) == "block"
    assert _driver_present(checks, "identity_fields_present", route="block")
    assert _driver_present(checks, "schema_validation", route="annotate")


def test_schema_drift_routes_warn(spec):
    """A whole-doc schema failure (extra top-level property under
    additionalProperties:false) → warn: schema_validation is staged as annotate during
    the trial window, so it warns rather than blocks. We assert the warn is DRIVEN by
    schema_validation routing annotate, not some incidental block-routed failure."""
    checks = _checks(spec, "variants/variant_schema_drift.json")
    assert qa_validate.compute_release_verdict(checks, traces=[]) == "warn"
    assert _driver_present(checks, "schema_validation", route="annotate")
