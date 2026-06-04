"""Tests for experiments/meeting_schedule/attachments/qa_checks.py.

Locks the discovered_schedule_location quality contract: agents that emit a
placeholder string or a per-meeting deep-link URL should trip a warning so
gp-api never persists a useless hint for the next run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Prevent importlib from writing __pycache__ alongside the source file —
# the source lives in experiments/meeting_schedule/attachments/qa_checks.py
# and the publisher rejects any subdirectory under attachments/ as malformed.
sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / "experiments" / "meeting_schedule" / "attachments" / "qa_checks.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("ms_validate", VALIDATOR_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ms_validate"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestDiscoveredScheduleLocation:
    """check_discovered_schedule_location nudges agents toward emitting a usable
    next-run hint. Warning-level (does not block release)."""

    def test_found_with_missing_field_warns(self):
        v = _load_validator()
        artifact = {"status": "found", "discovered_schedule_location": None}
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert len(findings) == 1
        f = findings[0]
        assert f.check == "discovered_schedule_location.missing"
        assert f.severity == "warning"

    def test_not_found_with_null_does_not_warn(self):
        """status='not_found' with null is legitimate: the agent couldn't
        find a schedule and has no plausible future-run starting point."""
        v = _load_validator()
        artifact = {"status": "not_found", "discovered_schedule_location": None}
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert findings == []

    def test_placeholder_text_warns(self):
        v = _load_validator()
        for placeholder in ("TBD", "unknown", "n/a", "N/A", "none", "?", "-"):
            artifact = {
                "status": "found",
                "discovered_schedule_location": placeholder,
            }
            findings: list = []
            v.check_discovered_schedule_location(artifact, findings)
            assert len(findings) == 1, f"expected warning for placeholder={placeholder!r}"
            assert findings[0].check == "discovered_schedule_location.placeholder"

    def test_suspiciously_short_string_warns(self):
        v = _load_validator()
        artifact = {"status": "found", "discovered_schedule_location": "abc"}
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert len(findings) == 1
        assert findings[0].check == "discovered_schedule_location.placeholder"

    def test_deep_link_metaviewer_warns(self):
        v = _load_validator()
        artifact = {
            "status": "found",
            "discovered_schedule_location": "https://city.granicus.com/MetaViewer.php?meta_id=12345",
        }
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert len(findings) == 1
        assert findings[0].check == "discovered_schedule_location.deep_link"

    def test_deep_link_legistar_matter_warns(self):
        v = _load_validator()
        artifact = {
            "status": "found",
            "discovered_schedule_location": "https://legistar.example.gov/LegislationDetail.aspx?ID=98765",
        }
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert len(findings) == 1
        assert findings[0].check == "discovered_schedule_location.deep_link"

    def test_valid_parent_url_passes(self):
        v = _load_validator()
        for url in (
            "https://example.gov/government/city-council/meetings",
            "https://library.municode.com/state/city/codes/code_of_ordinances?nodeId=2_04_010",
            "https://city.granicus.com/ViewPublisher.php?view_id=5",
            "https://example.gov/agendas-and-minutes/",
        ):
            artifact = {
                "status": "found",
                "discovered_schedule_location": url,
            }
            findings: list = []
            v.check_discovered_schedule_location(artifact, findings)
            assert findings == [], f"unexpected finding for url={url}"

    def test_municipal_code_pdf_passes(self):
        """A municipal-code PDF that codifies the meeting schedule is a fine
        parent doc — don't punish '.pdf' on its own (unlike the briefing's
        agenda-PDF check). Only the per-meeting deep-link patterns warn."""
        v = _load_validator()
        artifact = {
            "status": "found",
            "discovered_schedule_location": "https://example.gov/municipal-code/title-2/chapter-04.pdf",
        }
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert findings == []

    def test_non_string_value_is_silently_ignored(self):
        """Schema validation catches type errors elsewhere; the QA check
        should not raise on a malformed value."""
        v = _load_validator()
        artifact = {"status": "found", "discovered_schedule_location": 42}
        findings: list = []
        v.check_discovered_schedule_location(artifact, findings)
        assert findings == []


class TestRunDriver:
    """Smoke test the full run() driver against a minimal valid artifact and a
    minimal artifact with a known placeholder, so we know the orchestration
    (schema load → schema validate → checks) is wired correctly."""

    @staticmethod
    def _minimal_found_artifact(location: str | None = "https://example.gov/agendas") -> dict:
        return {
            "generated_at": "2026-06-04T12:00:00Z",
            "status": "found",
            "meeting_name": "City Council",
            "location": "City Hall Council Chambers, 200 Main St",
            "rrule": "FREQ=MONTHLY;BYDAY=2MO,4MO",
            "human": "Second and fourth Monday of every month",
            "time": "19:00",
            "timezone": "America/Denver",
            "duration_minutes": 120,
            "sources": [
                {"url": "https://example.gov/agendas", "note": "official agendas page"}
            ],
            "discovered_schedule_location": location,
        }

    def test_run_passes_on_clean_artifact(self, tmp_path):
        v = _load_validator()
        artifact_path = tmp_path / "meeting_schedule.json"
        import json as _json

        artifact_path.write_text(_json.dumps(self._minimal_found_artifact()))
        manifest_path = REPO_ROOT / "experiments" / "meeting_schedule" / "manifest.json"
        report = v.run(artifact_path, manifest_path=manifest_path)
        assert report.schema_valid, f"schema errors: {report.schema_errors}"
        assert report.errors == []
        assert report.warnings == []
        assert report.passed

    def test_run_warns_on_placeholder(self, tmp_path):
        v = _load_validator()
        artifact_path = tmp_path / "meeting_schedule.json"
        import json as _json

        artifact_path.write_text(
            _json.dumps(self._minimal_found_artifact(location="TBD"))
        )
        manifest_path = REPO_ROOT / "experiments" / "meeting_schedule" / "manifest.json"
        report = v.run(artifact_path, manifest_path=manifest_path)
        assert report.schema_valid
        assert report.errors == []
        assert len(report.warnings) == 1
        assert report.warnings[0].check == "discovered_schedule_location.placeholder"
        # Warnings don't fail the run.
        assert report.passed
