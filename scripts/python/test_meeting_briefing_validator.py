"""Tests for experiments/meeting_briefing/attachments/qa_checks.py.

Locks the discovery-depth contract claimed by instruction.md.

Near-term meetings (target <= PUBLISH_LAG_CUTOFF_DAYS out, or days-out
undetermined): the validator MUST reject awaiting_agenda / no_meeting_found
unless all 4 high-yield discovery channels (1-4) are represented in
run_metadata.run_decisions[] (via `channel_<N>_*` decision prefixes).

Beyond-cutoff meetings (target > PUBLISH_LAG_CUTOFF_DAYS out): the publish-lag
early-exit lets the agent short-circuit after channel 1, so only channel 1 is
required. Packets almost never exist that far out; exhausting channels 2-4
would be wasted spend.

The validator is the only thing standing between an agent that bails too early
and a published artifact that lies about depth of effort.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Prevent importlib from writing __pycache__ alongside the source file —
# the source lives in experiments/meeting_briefing/attachments/qa_checks.py
# and the publisher rejects any subdirectory under attachments/ as malformed.
# A leftover __pycache__ from running these tests would break `publish_experiments.py`.
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "experiments" / "meeting_briefing" / "attachments" / "qa_checks.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("mb_validate", VALIDATOR_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["mb_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


def _decision(channel_n: int) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": f"channel_{channel_n}_probed",
        "reason": "details",
    }


def _all_four_decisions() -> list[dict]:
    """The full near-term discovery set: channels 1-4."""
    return [_decision(n) for n in range(1, 5)]


# Date helpers for exercising the publish-lag relaxation. _days_out() reads
# meeting_date and generated_at off the artifact, so the tests stamp both.
_GENERATED_AT = "2026-05-30T12:00:00+00:00"


def _meeting_date(days_out: int) -> str:
    from datetime import date, timedelta
    base = date(2026, 5, 30)
    return (base + timedelta(days=days_out)).isoformat()


class TestAwaitingAgendaDiscoveryDepth:
    """Near-term meetings (days-out <= cutoff, or undetermined) require channels 1-4."""

    def test_awaiting_agenda_with_all_4_channels_passes(self):
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(3),  # near-term
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": _all_four_decisions()},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []

    def test_awaiting_agenda_missing_a_channel_fails(self):
        v = _load_validator()
        # drop channel 4 (the CDN-search channel — the Fulshear-pattern fix)
        decisions = [_decision(n) for n in range(1, 5) if n != 4]
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(3),  # near-term
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": decisions},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        f = findings[0]
        assert f.check == "run_decisions.discovery_channels_incomplete"
        assert f.severity == "error"
        assert "[4]" in f.message
        assert "channel_<N>_" in f.message

    def test_undetermined_days_out_defaults_to_strict_near_term(self):
        """No meeting_date / generated_at → _days_out() is None → fail closed:
        require all of channels 1-4, not the relaxed channel-1-only path."""
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "run_metadata": {"run_decisions": [_decision(1)]},  # only channel 1
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert "[2, 3, 4]" in findings[0].message

    def test_ten_channel_1_subplatforms_do_not_clear_the_gate(self):
        """The bot's compounding-problem case: an agent that runs 10 sub-platforms
        under channel 1 and emits 10 separate run_decisions entries (all with
        decision='channel_1_*') must NOT clear the validator just because the
        count is high. For a near-term meeting, channels 2-4 are still untouched.
        """
        v = _load_validator()
        decisions = [_decision(1) for _ in range(10)]  # 10 channel_1 entries, no others
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(2),  # near-term
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": decisions},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert "[2, 3, 4]" in findings[0].message

    def test_briefing_ready_skips_the_check(self):
        """Full-briefing branch: check does not apply. An agent that finds the
        packet on channel 1 shouldn't be punished for not probing channels 2-4."""
        v = _load_validator()
        artifact = {
            "briefing_status": "briefing_ready",
            "run_metadata": {"run_decisions": [_decision(1)]},  # just channel 1
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []

    def test_no_meeting_found_near_term_requires_all_4(self):
        """no_meeting_found uses the same near-term exhaustion gate."""
        v = _load_validator()
        artifact = {
            "briefing_status": "no_meeting_found",
            "meeting_date": _meeting_date(4),  # near-term
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": [_decision(1), _decision(2)]},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert "no_meeting_found" in findings[0].message
        assert "[3, 4]" in findings[0].message

    def test_unrelated_decisions_are_ignored_not_treated_as_channels(self):
        """Decisions without the channel_<N>_ prefix shouldn't accidentally
        count as channel attempts. e.g. `derived_city_for_narrative` is a
        normal decision, not a discovery channel."""
        v = _load_validator()
        decisions = _all_four_decisions() + [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": "derived_city_for_narrative",
                "reason": "Derived 'Cheyenne' from positionName",
            }
        ]
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(3),  # near-term
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": decisions},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []


class TestPublishLagEarlyExit:
    """Beyond-cutoff meetings (days-out > PUBLISH_LAG_CUTOFF_DAYS): the publish-lag
    early-exit lets awaiting_agenda stand with only channel 1 attempted."""

    def test_beyond_cutoff_channel_1_only_passes(self):
        """(a) awaiting_agenda accepted with only channel 1 when meeting is far out."""
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(21),  # well beyond the 7-day cutoff
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    _decision(1),
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "publish_lag_early_exit",
                        "reason": "target 21 days out (> 7-day cutoff); channel 1 empty; remaining channels skipped",
                    },
                ]
            },
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []

    def test_beyond_cutoff_still_requires_channel_1(self):
        """The early-exit relaxes channels 2-4 but NOT channel 1 — the agent must
        still have probed the primary platform before bailing."""
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(21),
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "publish_lag_early_exit",
                        "reason": "far out; skipped everything",
                    }
                ]
            },
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert findings[0].check == "run_decisions.discovery_channels_incomplete"
        assert "channel 1" in findings[0].message

    def test_exactly_at_cutoff_is_near_term(self):
        """days_out == cutoff is NOT beyond cutoff (strict '>'), so the full
        near-term channel-1-4 requirement applies."""
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(7),  # exactly the cutoff
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": [_decision(1)]},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert "[2, 3, 4]" in findings[0].message

    def test_beyond_cutoff_with_all_4_channels_also_passes(self):
        """An agent that probed all 4 channels for a far-out meeting is fine too —
        the relaxation lowers the floor, it doesn't forbid extra effort."""
        v = _load_validator()
        artifact = {
            "briefing_status": "awaiting_agenda",
            "meeting_date": _meeting_date(30),
            "generated_at": _GENERATED_AT,
            "run_metadata": {"run_decisions": _all_four_decisions()},
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []
