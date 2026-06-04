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
            "meeting_date": _meeting_date(21),  # well beyond the 5-day cutoff
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    _decision(1),
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "publish_lag_early_exit",
                        "reason": "target 21 days out (> 5-day cutoff); channel 1 empty; remaining channels skipped",
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
            "meeting_date": _meeting_date(5),  # exactly the cutoff
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


class TestStaleScheduleExemption:
    """Under PR #58 the agent VERIFIES a caller-supplied meetingDate rather than
    discovering the next meeting. When the platform shows no meeting on the
    target date, the agent emits `no_meeting_found` with a single
    `no_meeting_on_target_date` run-decision reason and never reaches packet
    discovery. Those artifacts are exempt from the channel-depth check entirely.
    """

    def test_no_meeting_on_target_date_is_exempt_from_channel_depth(self):
        v = _load_validator()
        artifact = {
            "briefing_status": "no_meeting_found",
            "meeting_date": _meeting_date(3),  # near-term — would otherwise require 1-4
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "no_meeting_on_target_date",
                        "reason": "no_meeting_on_target_date",
                    }
                ]
            },
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []

    def test_exemption_keys_on_reason_not_decision(self):
        """The exemption is recognized via the run-decision `reason` field
        (`no_meeting_on_target_date`), matching qa_checks `_STALE_SCHEDULE_REASONS`."""
        v = _load_validator()
        artifact = {
            "briefing_status": "no_meeting_found",
            "meeting_date": _meeting_date(2),
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "verified_target_date_no_meeting",
                        "reason": "no_meeting_on_target_date",
                    }
                ]
            },
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert findings == []

    def test_no_meeting_found_without_exemption_reason_still_requires_channels(self):
        """A near-term `no_meeting_found` that does NOT carry the stale-schedule
        reason still falls under the normal channel-1-4 exhaustion gate — the
        exemption must not become a blanket bypass for no_meeting_found."""
        v = _load_validator()
        artifact = {
            "briefing_status": "no_meeting_found",
            "meeting_date": _meeting_date(3),
            "generated_at": _GENERATED_AT,
            "run_metadata": {
                "run_decisions": [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision": "channel_1_streaming_platforms",
                        "reason": "checked the primary platform",
                    }
                ]
            },
        }
        findings: list = []
        v.check_awaiting_agenda_discovery_depth(artifact, findings)
        assert len(findings) == 1
        assert "[2, 3, 4]" in findings[0].message

    def test_stale_schedule_reasons_constant_present(self):
        """qa_checks must expose the exemption reason set so the contract is
        greppable and stays in sync with instruction.md Step 2."""
        v = _load_validator()
        assert "no_meeting_on_target_date" in v._STALE_SCHEDULE_REASONS


# ---------------------------------------------------------------------------
# Branch-aware schema validation (Lever 2)
#
# validate_schema() hands the WHOLE oneOf to Draft7Validator only when it can't
# unambiguously pick a branch. When briefing_status selects exactly one branch,
# errors must be scoped to THAT branch — not the merged "doesn't match Full AND
# doesn't match Placeholder" noise that sends the agent chasing phantoms.
# ---------------------------------------------------------------------------

MANIFEST_PATH = REPO_ROOT / "experiments" / "meeting_briefing" / "manifest.json"


def _output_schema() -> dict:
    import json

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return manifest["output_schema"]


def _valid_full_artifact() -> dict:
    """A minimal Full-branch artifact that satisfies the MeetingBriefingFull
    sub-schema (briefing_status='briefing_ready')."""
    return {
        "experiment_id": "meeting_briefing",
        "briefing_type": "city_council_meeting",
        "briefing_status": "briefing_ready",
        "generated_at": "2026-05-30T12:00:00Z",
        "official_name": "Jane Doe",
        "meeting_name": "City Council",
        "location": "City Hall",
        "meeting_date": "2026-06-02",
        "meeting_time": "19:00",
        "meeting_timezone": "America/New_York",
        "estimated_read_minutes": 8,
        "executive_summary": {"lead_in": "Items:", "items": []},
        "run_metadata": {
            "agenda_packet_url": "https://example.com/packet.pdf",
            "source_bundle_retrieved_at": "2026-05-30T11:00:00Z",
        },
        "items": [
            {
                "id": "item_001",
                "item_number": "5F",
                "title": "Some agenda item",
                "tier": "standard",
                "vote_required": False,
                "tier_reason": ["procedural"],
                "display": {"summary": "A summary."},
                "research": {
                    "raw_context": [
                        {
                            "chunk_id": "c1",
                            "item_id": "item_001",
                            "item_title": "Some agenda item",
                            "tier": "standard",
                            "source_id": "src_1",
                            "pages": [1],
                            "text": "context text",
                        }
                    ],
                    "full_treatment": None,
                },
            }
        ],
        "claims": [],
        "sources": [
            {
                "id": "src_1",
                "name": "Agenda packet",
                "source_type": "agenda_packet",
                "retrieved_at": "2026-05-30T11:00:00Z",
                "retrieved_text_or_snapshot": "context text",
            }
        ],
        "required_data_points": [],
        "disclosure": "Generated with AI assistance and may contain errors. modeled estimate.",
    }


def _valid_placeholder_artifact() -> dict:
    """A minimal Placeholder-branch artifact (briefing_status='awaiting_agenda')."""
    return {
        "experiment_id": "meeting_briefing",
        "briefing_type": "city_council_meeting",
        "briefing_status": "awaiting_agenda",
        "generated_at": "2026-05-30T12:00:00Z",
        "official_name": "Jane Doe",
        "meeting_name": "City Council",
        "location": "City Hall",
        "meeting_date": "2026-06-02",
        "meeting_time": "19:00",
        "meeting_timezone": "America/New_York",
        "estimated_read_minutes": 0,
        "executive_summary": {"lead_in": "Awaiting agenda.", "items": []},
        "run_metadata": {
            "agenda_packet_url": None,
            "source_bundle_retrieved_at": "2026-05-30T11:00:00Z",
        },
        "items": [
            {
                "id": "item_001",
                "item_number": None,
                "title": "Awaiting agenda",
                "tier": "standard",
                "vote_required": False,
                "tier_reason": ["placeholder"],
                "display": {
                    "summary": "The agenda packet has not been published yet.",
                    "constituent_sentiment": None,
                    "recent_news": None,
                    "budget_impact": None,
                    "talking_points": None,
                },
                "research": {
                    "raw_context": [
                        {
                            "chunk_id": "c1",
                            "item_id": "item_001",
                            "item_title": "Awaiting agenda",
                            "tier": "standard",
                            "source_id": "src_1",
                            "pages": [1],
                            "text": "context text",
                        }
                    ],
                    "full_treatment": None,
                },
            }
        ],
        "claims": [],
        "sources": [
            {
                "id": "src_1",
                "name": "Calendar page",
                "source_type": "government_website",
                "retrieved_at": "2026-05-30T11:00:00Z",
                "retrieved_text_or_snapshot": "context text",
            }
        ],
        "required_data_points": [],
        "disclosure": "Generated with AI assistance and may contain errors. modeled estimate.",
    }


class TestBranchAwareSchemaValidation:
    """Errors should be scoped to the branch selected by briefing_status."""

    def test_valid_full_artifact_passes(self):
        v = _load_validator()
        errors = v.validate_schema(_valid_full_artifact(), _output_schema())
        assert errors == [], f"valid Full artifact rejected: {errors}"

    def test_valid_placeholder_artifact_passes(self):
        v = _load_validator()
        errors = v.validate_schema(_valid_placeholder_artifact(), _output_schema())
        assert errors == [], f"valid Placeholder artifact rejected: {errors}"

    def test_placeholder_violation_yields_single_scoped_error(self):
        """A Placeholder artifact that violates a Placeholder-only constraint
        (claims maxItems:0) must produce ONE scoped error pointing at the
        offending field — NOT the merged top-level oneOf error that names both
        branches."""
        v = _load_validator()
        bad = _valid_placeholder_artifact()
        # Placeholder branch requires claims to be empty (maxItems: 0).
        bad["claims"] = [
            {
                "claim_id": "claim_001",
                "item_id": "item_001",
                "section": "overview",
                "claim_text": "x",
                "claim_type": "inferred",
                "claim_weight": "low",
                "source_extracts": ["x"],
                "source_ids": ["src_1"],
                "required_source_type": "none",
                "route_if_unsupported": "flag_as_inferred",
            }
        ]
        errors = v.validate_schema(bad, _output_schema())
        assert len(errors) == 1, f"expected one scoped error, got: {errors}"
        # The scoped error points at the claims path, not a top-level oneOf miss.
        assert "['claims']" in errors[0]
        # And it must NOT be the merged oneOf error.
        joined = " ".join(errors).lower()
        assert "is not valid under any of the given schemas" not in joined
        assert "oneof" not in joined

    def test_full_body_with_placeholder_status_yields_scoped_errors(self):
        """A Full-shaped body mislabeled with a Placeholder-branch status
        (awaiting_agenda) must produce errors scoped to the Placeholder branch
        the status selects, NOT the merged top-level oneOf error that names both
        branches. This is the headline lever2 behavior: scope errors to the
        branch briefing_status selects, even when the body fits the other one."""
        v = _load_validator()
        mislabeled = _valid_full_artifact()
        mislabeled["briefing_status"] = "awaiting_agenda"
        errors = v.validate_schema(mislabeled, _output_schema())
        assert errors, "expected the mislabeled Full body to fail Placeholder validation"
        joined = " ".join(errors).lower()
        # Scoped to the selected branch, not the merged full-oneOf signature.
        assert "is not valid under any of the given schemas" not in joined
        assert "oneof" not in joined
        # Errors point into the artifact body (the items the Placeholder branch
        # constrains), not a bare top-level oneOf miss.
        assert any("item" in e.lower() for e in errors), errors

    def test_ambiguous_missing_status_falls_back_without_crashing(self):
        """No briefing_status → no branch matches → fall back to full oneOf
        validation. Must not crash and should report the artifact as invalid.

        Crucially, the FALLBACK path must actually run: when no branch is
        selectable the validator runs the WHOLE oneOf, which emits the merged
        "is not valid under any of the given schemas" signature that the scoped
        path deliberately suppresses (see
        test_placeholder_violation_yields_single_scoped_error, which asserts the
        opposite). Asserting that signature is present proves we fell back to the
        full oneOf rather than silently picking a branch."""
        v = _load_validator()
        artifact = {"experiment_id": "meeting_briefing"}  # missing briefing_status
        errors = v.validate_schema(artifact, _output_schema())
        assert errors, "expected the malformed artifact to fail validation"
        joined = " ".join(errors).lower()
        assert "is not valid under any of the given schemas" in joined, (
            "expected the merged full-oneOf error signature, proving fallback to "
            f"the whole oneOf rather than a scoped branch. Got: {errors}"
        )

    def test_select_branch_returns_none_for_non_oneof(self):
        v = _load_validator()
        assert v._select_branch_schema({"briefing_status": "briefing_ready"}, {"type": "object"}) is None

    def test_select_branch_returns_none_when_two_branches_overlap(self):
        """When briefing_status matches more than one branch (overlapping enums),
        selection is ambiguous → return None → fall back to the full oneOf.
        Exercises the len(matches) > 1 path."""
        v = _load_validator()
        overlapping = {
            "oneOf": [
                {"properties": {"briefing_status": {"enum": ["briefing_ready", "shared"]}}},
                {"properties": {"briefing_status": {"enum": ["shared", "awaiting_agenda"]}}},
            ]
        }
        assert v._select_branch_schema({"briefing_status": "shared"}, overlapping) is None
