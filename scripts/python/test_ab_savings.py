"""Behavioral tests for ab_savings.render_verbatim — the end-of-A/B apples-to-apples
verbatim artifact dump (control v1 vs treatment v2, full content, no truncation)."""
import json

from ab_savings import render_verbatim


def test_verbatim_preserves_full_content_for_both_arms():
    ctrl = {"opportunities": ["Low win number of 739 ([Taylor County](http://x))"],
            "challenges": ["Short runway to November 3, 2026"]}
    treat = {"opportunities": ["Low win number of 739 (GoodParty.org Data)"],
             "challenges": ["Short runway to November 3, 2026"]}
    md = render_verbatim([("taylor_school", ctrl, treat)])

    # the input label heads its own section
    assert "taylor_school" in md
    # both arms are present and labeled
    assert "control" in md and "treatment" in md
    # VERBATIM: the exact, untruncated bullet strings from each arm appear
    assert "Low win number of 739 ([Taylor County](http://x))" in md
    assert "Low win number of 739 (GoodParty.org Data)" in md


def test_verbatim_marks_missing_artifact_and_orders_control_first():
    md = render_verbatim([("desoto", None, {"opportunities": ["a"], "challenges": ["b"]})])
    # a waiting/failed arm is shown as missing, not silently dropped
    assert "no artifact" in md.lower()
    # control is rendered before treatment so the diff reads left-to-right
    assert md.lower().index("control") < md.lower().index("treatment")


def test_verbatim_renders_each_input_in_dispatch_order():
    pairs = [("garland", {"opportunities": ["g"], "challenges": ["g2"]}, {"opportunities": ["G"], "challenges": ["G2"]}),
             ("ec899", {"opportunities": ["e"], "challenges": ["e2"]}, {"opportunities": ["E"], "challenges": ["E2"]})]
    md = render_verbatim(pairs)
    assert md.index("garland") < md.index("ec899")
