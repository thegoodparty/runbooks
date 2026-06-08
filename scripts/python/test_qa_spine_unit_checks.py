"""Layer 1 — per-check UNIT tests for the QA spine, against the unit packet.

This is the PM's primary ask: verify that each INDIVIDUAL deterministic check
function catches what it should (and does NOT fire when it should not), regardless
of how the whole briefing's overall release_verdict routes.

The unit packet (fixtures/qa_test_packet/unit_check_packet.json) is the clean
agent-assembled baseline with several targeted per-claim / per-item defects folded
into ONE file, each isolated so only its intended check reacts on its target. We run
the deterministic spine ONCE, then assert each check's individual result on its target
by check_id (+ offending). The packet's overall release_verdict is IRRELEVANT here and
is never asserted — that is the integration layer's job
(test_qa_spine_integration_verdict.py).

Every expectation below was calibrated by ACTUALLY RUNNING the validator offline
(`qa_validate.run_deterministic(artifact, spec, check_urls=False)`), never hand-guessed.
If a check's logic or thresholds change, this test fails and the unit packet / manifest
must be re-calibrated (see fixtures/qa_test_packet/README.md). requires_llm cases are
documented in the manifest but never asserted here — this test never calls a paid LLM.
"""
from __future__ import annotations

import pytest

from conftest import PACKET_DIR, run_offline_checks  # shared fixtures live in conftest.py

UNIT_PACKET = "unit_check_packet.json"


@pytest.fixture(scope="module")
def checks(spec):
    """Run the deterministic spine ONCE over the unit packet, offline, and return the
    full list of DeterministicCheck. The release_verdict is intentionally not computed
    or returned — unit assertions are per-check, not verdict-driven."""
    return run_offline_checks(spec, PACKET_DIR / UNIT_PACKET)


def _emissions(checks, check_id):
    """All emissions for a check_id (a check_id can emit more than once, e.g.
    source_hierarchy_policy emits a block AND a policy-gap diagnostic)."""
    return [c for c in checks if c.check_id == check_id]


# ── caught-defect targets ─────────────────────────────────────────────────────

def test_extract_not_in_source_is_caught(checks):
    """claim_008's source_extract is invented text absent from its cited
    src_streetscape snapshot → extracts_appear_in_cited_source fails/blocks on
    claim_008. Isolation: high_stakes_structured_match is NOT what fired."""
    grounding = _emissions(checks, "extracts_appear_in_cited_source")
    failing = [c for c in grounding if c.status == "fail" and c.route == "block"]
    assert failing, f"expected a block-routed fail; got {[(c.status, c.route) for c in grounding]}"
    assert any("claim_008" in (c.offending or "") for c in failing), (
        f"expected claim_008 in offending; got {[c.offending for c in failing]}"
    )
    # Isolation: the defect lands ONLY on the grounding check — the structured-match
    # check's failing/warning emissions must not name claim_008. (Filtering on offending
    # alone would be vacuous: structured_match never names claim_008 even when correct,
    # so the prior assertion could not fail. We assert across ALL its non-pass emissions.)
    assert all(
        "claim_008" not in (e.offending or "")
        for e in _emissions(checks, "high_stakes_structured_match")
        if e.status in ("fail", "warning")
    )


def test_money_mismatch_is_caught_by_structured_match(checks):
    """claim_004 collapses the $42M/$43.5M caps into an invented $45,000,000 figure
    absent from the cited source → high_stakes_structured_match fails on the missing
    45000000 literal. Isolation: the extract is left a verbatim substring, so
    extracts_appear_in_cited_source does not fail on claim_004."""
    sv = _emissions(checks, "high_stakes_structured_match")
    failing = [c for c in sv if c.status == "fail" and c.route == "block"]
    assert failing, f"expected a block-routed fail; got {[(c.status, c.route) for c in sv]}"
    assert any("claim_004(money): missing ['45000000']" in (c.offending or "") for c in failing), (
        f"expected the missing 45000000 literal; got {[c.offending for c in failing]}"
    )
    # Isolation: the defect lands ONLY on structured-match. claim_004's extract is left a
    # verbatim substring, so the grounding check's failing/warning emissions must not name
    # claim_004. (Asserted across ALL non-pass grounding emissions so the check is real:
    # grounding never names claim_004 even when correct, which made the prior form vacuous.)
    assert all(
        "claim_004" not in (e.offending or "")
        for e in _emissions(checks, "extracts_appear_in_cited_source")
        if e.status in ("fail", "warning")
    )


def test_budget_cited_to_news_is_caught_by_source_hierarchy(checks):
    """claim_005 (budget_number) is re-cited only to news source NEWS-1, outside its
    allowed [agenda_packet, government_website] → source_hierarchy_policy fails/blocks.
    Isolation: the $18,400,000 literal is planted in NEWS-1 with a matching extract, so
    high_stakes_structured_match and extracts_appear_in_cited_source both pass on it."""
    sh = _emissions(checks, "source_hierarchy_policy")
    failing = [c for c in sh if c.status == "fail" and c.route == "block"]
    assert failing, f"expected a block-routed fail; got {[(c.status, c.route) for c in sh]}"
    assert any(
        "claim_005(budget_number): ['NEWS-1=news'] not in ['agenda_packet', 'government_website']"
        in (c.offending or "")
        for c in failing
    ), f"expected the NEWS-1 hierarchy violation; got {[c.offending for c in failing]}"
    # Isolation: the defect lands ONLY on the hierarchy check. The $18,400,000 literal is
    # present and the extract is real, so neither structured-match nor grounding may name
    # claim_005 in ANY failing/warning emission. (Asserted across all non-pass emissions so
    # the check is real: neither check ever names claim_005 even when correct, which made
    # the prior `status == "fail" and "claim_005" in offending` filters vacuous.)
    assert all(
        "claim_005" not in (e.offending or "")
        for e in _emissions(checks, "high_stakes_structured_match")
        if e.status in ("fail", "warning")
    )
    assert all(
        "claim_005" not in (e.offending or "")
        for e in _emissions(checks, "extracts_appear_in_cited_source")
        if e.status in ("fail", "warning")
    )


def test_advocacy_in_authored_prose_is_flagged(checks):
    """The advocacy phrase 'Push for' is injected into item_001's authored
    display.summary, a policed prohibited_phrase_path → prohibited_phrases warns
    (annotate, never block)."""
    pp = _emissions(checks, "prohibited_phrases")
    warning = [c for c in pp if c.status == "warning" and c.route == "annotate"]
    assert warning, f"expected an annotate-routed warning; got {[(c.status, c.route) for c in pp]}"
    assert any("push_for" in (c.offending or "") for c in warning), (
        f"expected the push_for advocacy pattern; got {[c.offending for c in warning]}"
    )


# ── false-positive / should-NOT-fire targets (asserted per-check) ─────────────

def test_advocacy_inside_quoted_source_is_not_flagged(checks):
    """The advocacy phrase 'demand' appears only inside NEWS-2's source snapshot and
    claim_010's source_extract — never in an authored prose path. prohibited_phrases
    scans authored prose only, so the ONLY thing it flags is the authored 'Push for'
    on item_001: 'demand' must NOT appear in any prohibited_phrases finding."""
    pp = _emissions(checks, "prohibited_phrases")
    for c in pp:
        assert "demand" not in (c.offending or "").lower(), (
            f"prohibited_phrases fired on advocacy text confined to a quoted source: {c.offending!r}"
        )


def test_truncated_extract_is_not_flagged(checks):
    """claim_009 (budget_number) is fully supported but its extract is shortened to a
    tiny true snippet ('$54,500.00 under estimate'). It is still a verbatim substring
    and the money literals remain in the cited source, so the deterministic checks must
    NOT fail on claim_009 — the false-positive the Phase-1 LLM tends to raise."""
    grounding = _emissions(checks, "extracts_appear_in_cited_source")
    assert not [c for c in grounding if c.status == "fail" and "claim_009" in (c.offending or "")], (
        f"a true-but-short extract was flagged: {[c.offending for c in grounding]}"
    )
    sv = _emissions(checks, "high_stakes_structured_match")
    assert not [c for c in sv if c.status == "fail" and "claim_009" in (c.offending or "")]


def test_paraphrased_summary_warns_below_threshold_but_routes_diagnostic(checks):
    """The accurate-but-paraphrased-summary false positive lives on the baseline at
    item_005 and item_010: summary_source_coherence ACTUALLY flags them on a real
    below-threshold lexical signal, but only as a diagnostic (route=diagnostic), which
    never drives the verdict. The unit packet inherits both untouched.

    Strengthened beyond the route constant: a route check alone passes even if paraphrase
    detection breaks, since `route="diagnostic"` is hardcoded on the check. We assert the
    check genuinely FIRED on item_005 and item_010 — each appears in the warning's
    offending AND is recorded below_threshold in details.per_item with tfidf/containment
    under the reported thresholds — so the test fails if the coherence check stops
    flagging those items. We then keep the route assertion."""
    coh = _emissions(checks, "summary_source_coherence")
    assert coh, "expected a summary_source_coherence emission"
    flagged = [c for c in coh if c.status == "warning"]
    assert flagged, f"expected a coherence warning; got {[(c.status, c.route) for c in coh]}"

    # The realistic below-threshold signal must be assertable from details.per_item:
    # each target item is scored, recorded below_threshold, and under both thresholds.
    targets = ("item_005", "item_010")
    for target in targets:
        # The item must appear in the warning offending (the named below-threshold list).
        assert any(target in (c.offending or "") for c in flagged), (
            f"{target} not named in any coherence warning offending; "
            f"got {[c.offending for c in flagged]}"
        )
        # ...and be recorded below_threshold with a real low lexical signal in details.
        scored = None
        thresholds = None
        for c in flagged:
            det = c.details or {}
            thresholds = (det.get("tfidf_threshold"), det.get("containment_threshold"))
            for pi in det.get("per_item", []):
                if pi.get("item_id") == target:
                    scored = pi
                    break
            if scored is not None:
                break
        assert scored is not None, f"{target} not found in coherence details.per_item"
        assert scored.get("below_threshold") is True, (
            f"{target} not recorded below_threshold; got {scored}"
        )
        tfidf_t, contain_t = thresholds
        assert scored["tfidf_cosine"] < tfidf_t and scored["containment"] < contain_t, (
            f"{target} lexical signal not under both thresholds {thresholds}; got {scored}"
        )

    # Routing: despite firing, coherence must stay diagnostic (never block/annotate).
    for c in flagged:
        assert c.route == "diagnostic", (
            f"coherence must route diagnostic (never block/annotate); got {c.route!r}"
        )
