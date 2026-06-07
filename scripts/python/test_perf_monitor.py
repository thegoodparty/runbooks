"""Red/green tests for the real-time performance monitor's drift alarm.

The monitor gates the latest deployed dev runs and alarms when execution health drifts above
the experiment's derived baseline: the no-artifact failure rate climbs, or the FLAG rate
spikes. Pure decision so it's testable without S3.
"""
from perf_monitor import drift_alarm


def test_no_drift_no_alarm():
    r = drift_alarm(live_no_artifact_rate=0.15, live_flag_rate=0.10, baseline_no_artifact_rate=0.15)
    assert r["alarm"] is False
    assert r["reasons"] == []


def test_no_artifact_spike_alarms():
    r = drift_alarm(live_no_artifact_rate=0.40, live_flag_rate=0.05, baseline_no_artifact_rate=0.15)
    assert r["alarm"] is True
    assert any("no-artifact" in x.lower() for x in r["reasons"])


def test_flag_spike_alarms():
    r = drift_alarm(live_no_artifact_rate=0.05, live_flag_rate=0.60, baseline_no_artifact_rate=0.05)
    assert r["alarm"] is True
    assert any("flag" in x.lower() for x in r["reasons"])


def test_baseline_none_treated_as_zero():
    # A no-status experiment with no recorded baseline: any material no-artifact rate alarms.
    r = drift_alarm(live_no_artifact_rate=0.30, live_flag_rate=0.0, baseline_no_artifact_rate=None)
    assert r["alarm"] is True


def test_small_rise_within_tolerance_is_ok():
    r = drift_alarm(live_no_artifact_rate=0.20, live_flag_rate=0.10, baseline_no_artifact_rate=0.15)
    assert r["alarm"] is False  # 0.20 <= 0.15 + 0.10 tolerance
