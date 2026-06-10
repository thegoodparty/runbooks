"""Red/green tests for the performance gate (config-driven, per-experiment).

Cross-experiment grounding showed there is NO universal status field: meeting_briefing uses
`briefing_status`, meeting_schedule uses `status`, opposition_research and
opportunities_and_challenges have none. So the gate's one universal hard FAIL is "produced no
artifact"; any status-based failure is per-experiment config (`fail_values`), and thresholds
are per-experiment too. A run with no status field is judged on artifact-presence + ceilings.
"""
from perf_gate import evaluate, looks_like_run_id, DEFAULT_THRESHOLDS, NO_ARTIFACT

OK = {"cost": 3.0, "turns": 45, "tool_errors": 0}
BRIEFING_CFG = {"fail_values": ["error"], "thresholds": DEFAULT_THRESHOLDS}


def test_no_artifact_is_the_universal_hard_fail():
    assert evaluate(OK, NO_ARTIFACT)["verdict"] == "FAIL"


def test_configured_fail_value_fails():
    r = evaluate(OK, "error", BRIEFING_CFG)
    assert r["verdict"] == "FAIL"


def test_valid_status_passes_even_if_it_looks_terminal():
    # "found" is meeting_schedule's success; with a config that only fails on "error" it passes.
    assert evaluate(OK, "found", {"fail_values": ["error"], "thresholds": DEFAULT_THRESHOLDS})["verdict"] == "PASS"


def test_status_not_treated_as_failure_without_config():
    # Default config has no fail_values: only NO_ARTIFACT is universal, so a bare "error"
    # string is NOT auto-failed (the gate can't know per-experiment semantics without config).
    assert evaluate(OK, "error")["verdict"] == "PASS"


def test_no_status_field_healthy_run_passes():
    assert evaluate(OK, None)["verdict"] == "PASS"


def test_cost_over_ceiling_flags():
    r = evaluate({"cost": 10.0, "turns": 45, "tool_errors": 0}, None)
    assert r["verdict"] == "FLAG" and any("cost" in x.lower() for x in r["reasons"])


def test_turns_over_ceiling_flags():
    r = evaluate({"cost": 3.0, "turns": 200, "tool_errors": 0}, None)
    assert r["verdict"] == "FLAG" and any("turn" in x.lower() for x in r["reasons"])


def test_tool_errors_over_ceiling_flags():
    r = evaluate({"cost": 3.0, "turns": 45, "tool_errors": 9}, None)
    assert r["verdict"] == "FLAG" and any("error" in x.lower() for x in r["reasons"])


def test_no_artifact_outranks_a_flag():
    r = evaluate({"cost": 99.0, "turns": 999, "tool_errors": 9}, NO_ARTIFACT)
    assert r["verdict"] == "FAIL"


def test_per_experiment_thresholds_apply():
    # meeting_schedule is ~10x cheaper; a $2 run flags only under a tight per-exp ceiling.
    tight = {"fail_values": [], "thresholds": {"cost_max": 1.0, "turns_max": 80, "tool_errors_max": 2}}
    assert evaluate({"cost": 2.0, "turns": 30, "tool_errors": 0}, "found", tight)["verdict"] == "FLAG"


# The gate resolves the artifact by run_id derived from the trace FILENAME. A trace named
# anything other than <run_id>.jsonl makes every S3 lookup miss → a false 100% NO_ARTIFACT.
# looks_like_run_id() lets main() warn instead of silently failing the whole arm.
def test_uuid_run_id_filename_is_recognized():
    assert looks_like_run_id("019ea8a3-bb03-7448-9235-b8616e9bf645")
    assert looks_like_run_id("60ae671b-94ee-4b9d-9cc6-f744348cabe9")


def test_label_named_trace_is_flagged_as_not_a_run_id():
    # this is exactly the mistake that produced a fake 100% NO_ARTIFACT in practice
    assert not looks_like_run_id("briefing_ready-andrew")
    assert not looks_like_run_id("awaiting_agenda-nathan")
