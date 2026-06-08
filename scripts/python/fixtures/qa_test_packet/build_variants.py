"""Generate the QA-spine test fixtures from agent_assembled_baseline.json.

Two layers (see README.md):

  Layer 1 — ONE unit packet (unit_check_packet.json): the clean baseline plus
  several targeted per-claim / per-item defects, each isolated so that ONLY its
  intended check reacts on its target. The packet's overall release_verdict is
  irrelevant — the unit meta-test asserts each check's individual result on its
  target by check_id (+ offending), ignoring the verdict. Folding every per-claim
  defect into one file is sound precisely because the assertions are per-check.

  Layer 2 — a SMALL set of thin integration fixtures where release_verdict
  matters: one block-routed defect, one annotate-routed defect, a whole-doc
  identity-missing case, and a whole-doc schema-drift case. The clean baseline
  itself is the ok integration control.

This script OWNS (regenerates) exactly: unit_check_packet.json,
variants/variant_single_blocking_defect.json,
variants/variant_single_annotate_defect.json,
variants/variant_identity_missing.json, and variants/variant_schema_drift.json.
Any other variant_*.json under variants/ is NOT produced here and is left untouched.

Run from this directory:

    uv run python build_variants.py

Idempotent: overwrites only the files listed above each run. Every fixture is
fully synthetic (Lakemont / Jordan Avery / invented people).
No real record is the subject of a planted defect. This is the input record for
the defects; the manifest's expected per-check results / verdicts are calibrated
by ACTUALLY running qa_validate.py on the output (never hand-guessed).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = HERE / "agent_assembled_baseline.json"
UNIT_PACKET = HERE / "unit_check_packet.json"
VARIANTS = HERE / "variants"


def load_baseline() -> dict:
    return json.loads(BASELINE.read_text())


def get_claim(art: dict, claim_id: str) -> dict:
    try:
        return next(c for c in art["claims"] if c["claim_id"] == claim_id)
    except StopIteration:
        raise KeyError(f"no claim with claim_id={claim_id!r} in baseline") from None


def get_item(art: dict, item_id: str) -> dict:
    try:
        return next(it for it in art["items"] if it["id"] == item_id)
    except StopIteration:
        raise KeyError(f"no item with id={item_id!r} in baseline") from None


def get_source(art: dict, source_id: str) -> dict:
    try:
        return next(s for s in art["sources"] if s["id"] == source_id)
    except StopIteration:
        raise KeyError(f"no source with id={source_id!r} in baseline") from None


def write_json(path: Path, art: dict) -> None:
    path.write_text(json.dumps(art, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path.relative_to(HERE)}")


# ── per-claim / per-item defect injectors (composable into one packet) ────────
# Each mutates a DISTINCT claim/item/source so several can coexist in one file
# without colliding. Each is crafted so only its intended check reacts on its
# own target; literal consistency is preserved everywhere else.


def inject_extract_not_in_source(art: dict) -> None:
    """claim_008 (high-weight budget_number, item_009): replace its source_extract
    with text that is NOT in the cited src_streetscape snapshot (and not a money
    literal). claim_text is unchanged, so high_stakes_structured_match still passes
    — only extracts_appear_in_cited_source fails/blocks on claim_008."""
    c = get_claim(art, "claim_008")
    c["source_extracts"] = [
        "The selection committee unanimously praised the bidder's safety record and "
        "community references during the closed-session debrief."
    ]


def inject_money_mismatch(art: dict) -> None:
    """claim_004 (high-weight budget_number, item_007): collapse the $42M net-proceeds
    cap and $43.5M principal cap into a single invented $45,000,000 figure absent from
    the cited source. The source_extract is left a verbatim substring, so
    extracts_appear_in_cited_source still passes — only high_stakes_structured_match
    (money) fails/blocks on claim_004 for the missing 45000000 literal."""
    c = get_claim(art, "claim_004")
    c["claim_text"] = (
        "Resolution 26-R-081 authorizes sewer revenue bonds with a single cap of "
        "$45,000,000 covering both net proceeds and principal."
    )
    # source_extract left as-is: still a real substring of src_res_26R081.


def inject_budget_cited_to_news(art: dict) -> None:
    """claim_005 (high-weight budget_number, item_007): re-cite the $18,400,000
    trunk-line figure to news source NEWS-1, outside its allowed [agenda_packet,
    government_website]. Plant the exact literal into NEWS-1's snapshot and provide a
    matching extract, so high_stakes_structured_match and extracts_appear_in_cited_source
    both pass — only source_hierarchy_policy fails/blocks on claim_005.

    Uses claim_005 (not claim_008) so it does not collide with the extract-not-in-source
    defect on claim_008 in the same packet."""
    c = get_claim(art, "claim_005")
    c["source_ids"] = ["NEWS-1"]
    c["source_extracts"] = [
        "the Riverside trunk-line work alone is budgeted at $18,400,000, the Tribune reported"
    ]
    news = get_source(art, "NEWS-1")
    news["retrieved_text_or_snapshot"] = (
        news["retrieved_text_or_snapshot"]
        + " In a budget breakdown, the Riverside trunk-line work alone is budgeted at "
        "$18,400,000, the Tribune reported."
    )


def inject_advocacy_in_authored_prose(art: dict) -> None:
    """Inject the prohibited advocacy phrase 'Push for' into a policed authored prose
    path (item_001 display.summary; procedural item with no claims/literals to disturb
    other checks). prohibited_phrases scans display.summary, so it warns/annotates."""
    it = get_item(art, "item_001")
    it["display"]["summary"] = (
        "Procedural opening: the Council should Push for a quick roll call and approve "
        "the agenda as posted before moving to substantive items."
    )


def inject_truncated_extract(art: dict) -> None:
    """FALSE-positive target. claim_009 (high-weight budget_number, item_009) is fully
    supported, but its extract is shortened to a tiny true snippet. It is still a
    verbatim substring and the money literals stay in the cited source, so the
    deterministic checks (extracts_appear_in_cited_source, high_stakes_structured_match)
    must still PASS on claim_009. Phase-1 LLM tends to over-flag a thin snippet; the
    deterministic spine must not."""
    c = get_claim(art, "claim_009")
    c["source_extracts"] = ["$54,500.00 under estimate"]


def inject_advocacy_inside_quoted_source(art: dict) -> None:
    """FALSE-positive target. Put an advocacy phrase ('demand') only inside a source
    snapshot (NEWS-2) and a claim's source_extract (claim_010, low-weight news_context
    on item_009) — never in an authored prose path. prohibited_phrases scans authored
    prose only, so it must NOT fire; the extract is a real substring so grounding passes.

    Uses NEWS-2 / claim_010 so it does not collide with the budget_cited_to_news defect
    on NEWS-1 / claim_005."""
    news = get_source(art, "NEWS-2")
    quoted = (
        " One downtown merchant told the Tribune, \"We demand that the City keep the "
        "construction season short,\" at a recent meeting."
    )
    news["retrieved_text_or_snapshot"] = news["retrieved_text_or_snapshot"] + quoted
    c = get_claim(art, "claim_010")
    c["source_extracts"] = [
        "We demand that the City keep the construction season short"
    ]


# NOTE on the accurate-but-paraphrased-summary FALSE-positive target:
# The clean baseline already trips summary_source_coherence as a diagnostic on item_005
# and item_010 (faithful paraphrase). The unit packet inherits those untouched, so the
# unit test asserts the diagnostic-not-block behavior directly on the packet. No new
# injection needed (the task says to reuse the baseline's existing cases).


# ── Layer 1 — the single unit packet ─────────────────────────────────────────

def build_unit_check_packet() -> None:
    art = load_baseline()
    inject_extract_not_in_source(art)          # claim_008  -> extracts_appear_in_cited_source FAIL
    inject_money_mismatch(art)                 # claim_004  -> high_stakes_structured_match FAIL
    inject_budget_cited_to_news(art)           # claim_005  -> source_hierarchy_policy FAIL
    inject_advocacy_in_authored_prose(art)     # item_001   -> prohibited_phrases WARN
    inject_truncated_extract(art)              # claim_009  -> all deterministic PASS (false-pos)
    inject_advocacy_inside_quoted_source(art)  # NEWS-2/claim_010 -> prohibited_phrases NO fire (false-pos)
    # item_005 / item_010 faithful-paraphrase coherence diagnostic: inherited from baseline.
    write_json(UNIT_PACKET, art)


# ── Layer 2 — thin integration fixtures (release_verdict matters) ─────────────

def build_variant_single_blocking_defect() -> None:
    """Exactly one block-routed defect → verdict block. Reuses the extract-not-in-source
    family (the only hard block observed in the 488-briefing replay): claim_008's extract
    is absent from its cited source, so extracts_appear_in_cited_source blocks."""
    art = load_baseline()
    inject_extract_not_in_source(art)
    write_json(VARIANTS / "variant_single_blocking_defect.json", art)


def build_variant_single_annotate_defect() -> None:
    """Exactly one annotate-routed defect → verdict warn. The advocacy phrase 'Push for'
    in an authored display.summary makes prohibited_phrases annotate (never block)."""
    art = load_baseline()
    inject_advocacy_in_authored_prose(art)
    write_json(VARIANTS / "variant_single_annotate_defect.json", art)


def build_variant_identity_missing() -> None:
    """Whole-doc identity check → verdict block. official_name blanked, so
    identity_fields_present blocks (and schema_validation flags the minLength violation)."""
    art = load_baseline()
    art["official_name"] = ""
    write_json(VARIANTS / "variant_identity_missing.json", art)


def build_variant_schema_drift() -> None:
    """Whole-doc schema check → verdict warn. An extra top-level property violates
    additionalProperties:false; schema_validation is staged as annotate (warn), not block."""
    art = load_baseline()
    art["draft_notes"] = "internal scratch note that must not appear in a conforming artifact"
    write_json(VARIANTS / "variant_schema_drift.json", art)


def main() -> None:
    VARIANTS.mkdir(exist_ok=True)
    # Layer 1
    build_unit_check_packet()
    # Layer 2
    build_variant_single_blocking_defect()
    build_variant_single_annotate_defect()
    build_variant_identity_missing()
    build_variant_schema_drift()


if __name__ == "__main__":
    main()
