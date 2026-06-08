"""Shared fixtures and helpers for the QA-spine test suite.

The QA-spine unit (test_qa_spine_unit_checks.py) and integration
(test_qa_spine_integration_verdict.py) tests both load the same product spec and
run the deterministic spine offline against fixtures under fixtures/qa_test_packet.
The shared paths, the module-scoped `spec` fixture, and the offline-run helper live
here so the two files do not duplicate them.
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

import qa_validate

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "meeting_briefing_product_spec.json"
PACKET_DIR = HERE / "fixtures" / "qa_test_packet"


@pytest.fixture(scope="module")
def spec() -> dict:
    return qa_validate.load_product_spec(SPEC_PATH)


def run_offline_checks(spec: dict, path: Path) -> list:
    """Mirror `qa_validate.py <artifact> --no-llm --no-check-urls`: load the artifact
    plus its load-time checks, run the deterministic spine with URL liveness off, and
    return the combined list of DeterministicCheck. stderr is redirected so progress
    chatter does not pollute test output."""
    artifact, load_checks = qa_validate.load_artifact(path)
    with contextlib.redirect_stderr(io.StringIO()):
        return load_checks + qa_validate.run_deterministic(artifact, spec, check_urls=False)
