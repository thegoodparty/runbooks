"""Red/green tests for the offline external-faithfulness checker (candidate Gate B3).

The contract: extract identity figures (money, percent, legal citation, date) from a
claim's text, normalize, and confirm each appears in the *cited source's* captured text.
This is the external check the rubric's Gate B2 explicitly does not do (B2 only compares a
claim to its own embedded source_extract, which an optimizer can fake on both sides).
"""
from faithfulness_check import (
    extract_identity_tokens,
    verify_claim,
    faithfulness_gate,
)


def test_extracts_money_token():
    toks = extract_identity_tokens(
        "approved an initial residential program rate of $4.00 per month"
    )
    assert "$4.00" in toks


def test_true_money_figure_verified():
    r = verify_claim(
        "approved a rate of $4.00 per month",
        "Residential Customers: A fixed initial rate of $4.00 per month.",
    )
    assert r["verified"] is True
    assert r["missing"] == []


def test_fabricated_money_figure_caught():
    # The claim says $40.00; the captured source only ever said $4.00.
    # Internal-only B2 would pass this if the extract were also faked; B3 against the
    # real source must catch it.
    r = verify_claim(
        "approved a rate of $40.00 per month",
        "Residential Customers: A fixed initial rate of $4.00 per month.",
    )
    assert r["verified"] is False
    assert "$40.00" in r["missing"]


def test_thousands_separator_normalized():
    # Claim writes the comma, source omits it; normalization must reconcile $292,000 == $292000.
    r = verify_claim(
        "a side-by-side comparison ($292,000/year)",
        "the annual program cost is $292000 per year",
    )
    assert r["verified"] is True


def test_near_miss_money_not_falsely_verified():
    # Precision guard: a fabricated $40.00 must NOT verify against a source mentioning $14.00.
    r = verify_claim(
        "a rate of $40.00 per month",
        "a surcharge of $14.00 and a base of $4.00 apply",
    )
    assert r["verified"] is False
    assert "$40.00" in r["missing"]


def test_legal_citation_verified():
    r = verify_claim(
        "the statutory deadline (per Utah Code 54-17-903(3))",
        "as established in Utah Code 54-17-903(3), the program deadline is fixed",
    )
    assert r["verified"] is True


def test_money_matched_by_value_despite_format():
    # Claim "$950,000"; packet writes it bare with cents "950000.00". Same amount.
    r = verify_claim(
        "the project total cost is $950,000",
        "PROJECT LEDGER\n      950000.00 TOTAL AMOUNT",
    )
    assert r["verified"] is True


def test_small_money_not_value_matched_to_bare_number():
    # Precision guard: "$5" must NOT verify against an incidental "5" (e.g. a page number).
    r = verify_claim(
        "a filing fee of $5",
        "see page 5 of the staff report for details",
    )
    assert r["verified"] is False


def test_named_month_date_verified():
    r = verify_claim(
        "the statutory deadline to keep Kearns is June 2, 2026",
        "participants must respond on or before June 2, 2026 or be removed",
    )
    assert r["verified"] is True


def test_date_with_ordinal_suffix_in_source_verified():
    # Claim writes "May 13, 2026"; the packet writes "May 13th, 2026". Same date.
    r = verify_claim(
        "On May 13, 2026, the committee adopted the statement",
        "minutes of the meeting held on May 13th, 2026.",
    )
    assert r["verified"] is True


def test_vote_tally_not_extracted_as_legal_citation():
    # "15-9-1" is a vote tally, not a statute; it must not be pulled as an identity token.
    toks = extract_identity_tokens("recommended REFERRAL by a vote of 15-9-1")
    assert "15-9-1" not in toks


def test_real_legal_citation_with_cue_still_extracted():
    # Guard: a genuine citation (cued by "Code") must still be extracted.
    toks = extract_identity_tokens("the deadline per Utah Code 54-17-903(3) is fixed")
    assert any("54-17-903" in t for t in toks)


def _artifact(claim_text, snapshot):
    return {
        "items": [{"id": "i1", "tier": "featured"}],
        "claims": [
            {
                "claim_id": "c1",
                "item_id": "i1",
                "claim_text": claim_text,
                "claim_type": "budget",
                "required_source_type": "agenda_packet",
                "source_ids": ["s1"],
            }
        ],
        "sources": [
            {
                "id": "s1",
                "source_type": "agenda_packet",
                "retrieved_text_or_snapshot": snapshot,
            }
        ],
    }


def test_gate_dq_when_packet_claim_unverified():
    art = _artifact("rate of $40.00 per month", "A fixed initial rate of $4.00 per month.")
    res = faithfulness_gate(art)
    assert res["verdict"] == "DQ-faithfulness"
    assert any(c["claim_id"] == "c1" for c in res["unverified"])


def test_gate_pass_when_all_verified():
    art = _artifact("rate of $4.00 per month", "A fixed initial rate of $4.00 per month.")
    res = faithfulness_gate(art)
    assert res["verdict"] == "PASS"
    assert res["unverified"] == []
    assert res["coverage"] == 1.0


def test_gate_uses_injected_source_resolver_over_embedded_snapshot():
    # Gaming-resistant mode: the embedded snapshot is faked to $40.00, but the
    # resolver (standing in for the runner-persisted raw download) still says $4.00.
    art = _artifact("rate of $40.00 per month", "A fixed initial rate of $40.00 per month.")
    raw = {"s1": "A fixed initial rate of $4.00 per month."}
    res = faithfulness_gate(art, source_text_for=lambda sid: raw[sid])
    assert res["verdict"] == "DQ-faithfulness"
