"""Red/green tests for the performance gate.

The gate is the objective head of the two-headed eval: it judges HOW a run executed,
not whether the output is good. Hard FAIL is reserved for the one unambiguous failure
(the run produced no valid artifact); cost/turns/tool-error ceilings are FLAGs for review,
because a legitimately complex run may cost more without being wrong.
"""
from perf_gate import evaluate, DEFAULT_THRESHOLDS

OK = {"cost": 3.0, "turns": 45, "tool_errors": 0}


def test_no_artifact_is_hard_fail():
    r = evaluate({**OK}, status="NO_ARTIFACT")
    assert r["verdict"] == "FAIL"
    assert any("artifact" in reason.lower() for reason in r["reasons"])


def test_error_status_is_hard_fail():
    r = evaluate({**OK}, status="error")
    assert r["verdict"] == "FAIL"


def test_healthy_run_passes():
    r = evaluate({"cost": 3.0, "turns": 45, "tool_errors": 0}, status="awaiting_agenda")
    assert r["verdict"] == "PASS"
    assert r["reasons"] == []


def test_cost_over_ceiling_flags_not_fails():
    r = evaluate({"cost": 10.92, "turns": 50, "tool_errors": 0}, status="briefing_ready")
    assert r["verdict"] == "FLAG"
    assert any("cost" in reason.lower() for reason in r["reasons"])


def test_turns_over_ceiling_flags():
    r = evaluate({"cost": 4.0, "turns": 126, "tool_errors": 0}, status="briefing_ready")
    assert r["verdict"] == "FLAG"
    assert any("turn" in reason.lower() for reason in r["reasons"])


def test_tool_errors_over_ceiling_flags():
    r = evaluate({"cost": 4.0, "turns": 50, "tool_errors": 3}, status="awaiting_agenda")
    assert r["verdict"] == "FLAG"
    assert any("error" in reason.lower() for reason in r["reasons"])


def test_no_artifact_outranks_a_flag():
    # A run can be both over-ceiling AND have no artifact; FAIL must win.
    r = evaluate({"cost": 10.92, "turns": 126, "tool_errors": 3}, status="NO_ARTIFACT")
    assert r["verdict"] == "FAIL"


def test_thresholds_are_overridable():
    tight = {**DEFAULT_THRESHOLDS, "cost_max": 1.0}
    r = evaluate({"cost": 3.0, "turns": 45, "tool_errors": 0}, status="awaiting_agenda", thresholds=tight)
    assert r["verdict"] == "FLAG"
