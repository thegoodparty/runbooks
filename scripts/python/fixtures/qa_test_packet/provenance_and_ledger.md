# Provenance and ledger: agent-assembled QA golden fixture

Records where the synthetic baseline's agenda forms came from, what each fixture plants,
and the buggy-check findings surfaced during calibration. Companion to
`qa_test_packet_manifest.json` (the machine-readable ground truth) and the two meta-tests
`scripts/python/test_qa_spine_unit_checks.py` (per-check unit layer) and
`scripts/python/test_qa_spine_integration_verdict.py` (whole-artifact verdict layer).

## Unit-vs-integration split (packet 3.0)

The defect suite is organized in two layers. **Layer 1 (unit)** folds the per-claim /
per-item defects into ONE file, `unit_check_packet.json`, and the unit meta-test asserts
each check's result on its own target by `check_id` + `offending`, IGNORING the packet's
overall verdict. This is the primary ask (verify each check function in isolation). Folding
is sound precisely because the assertions are per-check, not verdict-driven; the unit packet's
overall verdict (block) is irrelevant. **Layer 2 (integration)** keeps a small set of thin,
single-condition fixtures where `release_verdict` is the point. The earlier one-defect-per-file
variants that existed only for verdict isolation were removed; their per-check cases now live in
the unit packet, and the verdict cases are covered by the thin integration fixtures. The
roadmap-gap cases (prioritization, actionability, toxic, PII, register, true-but-wrong-citation)
have no check function to unit-test, so their standalone variant files were removed and they are
kept as documentation-only `proposed_check` entries in the manifest.

Everything committed here is fully synthetic. Real S3 runs live only in the gitignored
`.reference_docs/mb_runs/` scratch and are never committed. No real person, place, or
record is the subject of a planted defect. The fixture's invented jurisdiction
(Lakemont), official (Jordan Avery), and named people stand in for any real subject.

## How the clean baseline was produced

`agent_assembled_baseline.json` is a genuine `briefing_ready` artifact assembled by a
clean-context sub-agent that followed the offline-adapted meeting_briefing assembly brief
over the synthetic hybrid agenda packet `hybrid_agenda_packet.md`. Generation is
non-deterministic, so it is snapshotted once.
It carries 15 items, 16 claims, and 13 sources spanning `agenda_packet`, `news`, and
`haystaq` source types. Calibrated verdict: **ok** (two benign diagnostics, below).

The baseline is a frozen committed snapshot: the source S3 runs live only in the gitignored
`.reference_docs/` scratch and are intentionally not reproducible by others; treat the
committed JSON as the ground truth.

## Source-run provenance (which real runs contributed which agenda forms)

The hybrid packet stitches *agenda shapes* (resolutions, consent agenda, budget/bond items,
staff recommendations, rezone public hearing, fee adjustments, settlement, appointments)
adapted in STRUCTURE (not content) from the `briefing_ready` runs pulled to
`.reference_docs/mb_runs/`. All names, figures, dates, vote counts, and legal citations
were replaced with invented Lakemont values before any briefing was generated, so no real
PII ever entered the artifact.

| Real run_id (scratch only) | Status | Shape | Agenda form contributed to the hybrid packet |
|---|---|---|---|
| `019e70da-f2b6-7000-a6aa-f1df0aa9cc39` | briefing_ready (13 items / 13 claims) | richest packet | overall multi-item agenda skeleton; consent agenda; received-and-filed CIP status |
| `019e70da-0c36-7000-a699-56c27e57d412` | briefing_ready (5 items / 10 claims) | budget-heavy | revenue-bond resolution + budget_impact figure tables; fee-adjustment items |
| `019e70db-4104-7000-a6b3-4b959fefce3f` | briefing_ready (10 items / 6 claims) | land-use heavy | rezone public-hearing form; planning-commission vote-count form |
| `019e70db-b5b6-7000-a6c0-3fb563688f12` | briefing_ready (5 items / 6 claims) | appointments/personnel | interim-manager appointment; settlement/personnel-matter form |

The non-`briefing_ready` runs in the scratch folder (`awaiting_agenda`, `no_meeting_found`)
contributed nothing; they have no items/claims to adapt.

## Layer 1, unit packet ledger (per-check, verdict-agnostic)

`unit_check_packet.json` derives from `agent_assembled_baseline.json` (built by
`build_variants.py`) and folds several defects into one file, each on a DISTINCT
claim/item/source so they coexist without colliding. The unit meta-test asserts each row
below on its own target by `check_id` + `offending`, ignoring the packet's overall verdict.
Expectations were calibrated by running `qa_validate.run_deterministic` on the packet.

| Target (in unit_check_packet.json) | Defect family | Rubric dimension | Check + expected result | Kind |
|---|---|---|---|---|
| claim_008 | extract not in cited source | Grounding & Traceability | `extracts_appear_in_cited_source` fail/block | caught |
| claim_004 | money literal / collapsed thresholds ($45M) | Accuracy | `high_stakes_structured_match` fail/block | caught |
| claim_005 | budget_number ($18.4M) re-cited to NEWS-1 | Grounding & Traceability | `source_hierarchy_policy` fail/block | caught |
| item_001 | advocacy 'Push for' in authored summary | Gating: no political advocacy | `prohibited_phrases` warning/annotate | caught |
| claim_009 | true-but-truncated extract | Accuracy | `extracts_appear_in_cited_source` + `high_stakes_structured_match` PASS (no fail on claim_009) | false positive |
| NEWS-2 / claim_010 | advocacy 'demand' inside a quoted source | Gating: no political advocacy | `prohibited_phrases` does NOT fire ('demand' absent from all findings) | false positive |
| item_005 / item_010 | faithful paraphrase | Grounding & Traceability | `summary_source_coherence` warning/**diagnostic** (never block) | false positive |

Isolation choices worth noting: the extract defect uses claim_008 while the budget-to-news
defect uses claim_005 (both budget_number, but distinct claims) so they do not collide; the
quoted-source advocacy false positive uses NEWS-2/claim_010 so it does not collide with the
budget-to-news defect on NEWS-1/claim_005. The faithful-paraphrase false positive is inherited
untouched from the baseline (item_005/item_010 trip `summary_source_coherence` as a diagnostic).

## Layer 2, integration fixtures ledger (whole-artifact verdict)

Each derives from the baseline with exactly one condition; the integration meta-test asserts
the `release_verdict`. Calibrated with `qa_validate.py --no-llm --no-check-urls`.

| Fixture file (committed-synthetic) | Condition | Driving check (route) | Expected verdict |
|---|---|---|---|
| `agent_assembled_baseline.json` | none (clean control) | none (only benign diagnostics) | ok |
| `variants/variant_single_blocking_defect.json` | claim_008 extract not in cited source | `extracts_appear_in_cited_source` (block) | block |
| `variants/variant_single_annotate_defect.json` | 'Push for' in item_001 authored summary | `prohibited_phrases` (annotate) | warn |
| `variants/variant_identity_missing.json` | official_name blanked | `identity_fields_present` (block) | block |
| `variants/variant_schema_drift.json` | extra top-level property `draft_notes` | `schema_validation` (annotate, staged) | warn |

## Roadmap-gap cases (documentation-only, no runnable fixture)

These rubric gaps have no check function to unit-test, so their standalone variant files were
removed in the packet-3.0 refactor. They remain in the manifest as `fails_not_yet_caught` with a
`proposed_check`: true-but-wrong-citation (Grounding, citation-discipline policy), prioritization
(salience), actionability (preparation value), toxic/discriminatory gate, inappropriate-PII gate,
professional-register gate.

## Buggy-check findings (recorded, not fixed)

These are check behaviors surfaced during calibration. Per the project rule we record them
here and do not modify check logic in this workstream.

1. **`source_hierarchy_policy` has no policy entry for several real claim_types.** On the
   clean baseline the check emits a `diagnostic` warning for `constituent_sentiment`,
   `news_context`, and `staff_recommendation`, none of which have a `source_hierarchy`
   entry in `meeting_briefing_product_spec.json` (only `budget_number`, `vote_count`,
   `legal_citation`, `date_or_deadline` are declared). The spine therefore cannot enforce
   appropriate provenance for those types (e.g. a `staff_recommendation` cited to a campaign
   page raises only a gap diagnostic, never a block).
   The diagnostic route is correct (not a silent allow), but the policy is incomplete.

2. **`summary_source_coherence` flags faithful paraphrase as low-coherence.** On the clean
   baseline, item_005 (tfidf 0.243, contain 0.250, emb 0.699) and item_010 (tfidf 0.288,
   contain 0.276, emb 0.755) fall below the lexical thresholds even though both summaries
   are faithful syntheses of their sources. The embedding rescue does not save them: item_005
   is below the 0.70 rescue threshold, and item_010 is ABOVE it (0.755) but rescue is
   forbidden because the item carries a `budget_number` claim (on the embedding rescue
   blocklist). The TF-IDF IDF term is degenerate over the N=2 strings compared, which
   down-weights shared tokens, backwards for a support signal. This is why the check is
   `diagnostic`-only and does not drive the verdict; it would over-flag faithful paraphrase
   if it were verdict-bearing. These are the canonical coherence false-positive cases.

3. **`completeness_floor` schema-path bug (cross-reference; does NOT fire here).** The
   2026-05-29 488-briefing audit confirmed a bug where `completeness_floor` measured the
   executive-summary length against a hard-coded field path that did not match the flattened
   `executive_summary.items[].overview` shape, silently undercounting. The current spec
   resolves this via `completeness.field_paths` (decoupled, skip-with-warning when paths are
   absent). On this baseline the paths resolve correctly and `completeness_floor` passes, so
   the historical bug does NOT manifest on this fixture, noted so a future reviewer does not
   re-diagnose it here.

4. **Gemini Phase-2 key-name mismatch (infra finding).** The Phase-2 escalation judge reads
   its API key from the literal lowercase-hyphenated env name `gemini-qa-agent`
   (`_resolve_api_key` in `qa_validate.py`), with `GEMINI_API_KEY` / `GOOGLE_API_KEY`
   fallbacks. A prior run failed Phase 2 because the key was exported under a different name.
   This does not affect the deterministic meta-test (which runs `--no-llm`), but any
   `requires_llm` case below must be confirmed with the key exported under one of those
   names. Production uses the same-family Anthropic Phase-1/Phase-2 path, where this does
   not apply.

## LLM-dependent cases

Some cases describe behavior that only the Phase 1/2 LLM judges catch; they are marked
`requires_llm` / `expected_llm` in the manifest and are NEVER auto-asserted (neither meta-test
calls a paid LLM):

- `falsepos_truncated_extract_does_not_block` (unit): the DETERMINISTIC result IS asserted
  (claim_009 must not fail); the documented Phase-1-over-flag / Phase-2-overturn tendency
  (45/60 such Phase-1 not-OKs overturned in the 488-run) is not.
- `grounding_true_but_wrong_citation_annotates_only` (roadmap gap): no runnable fixture; an
  LLM reading all snapshots would mark it "Not in Source, Verified Elsewhere".

To explore the LLM behavior, run `qa_validate.py` without `--no-llm` (incurs cost; requires the
judge API keys, see finding 4).

## Reproducing

```bash
cd scripts/python/fixtures/qa_test_packet
uv run python build_variants.py            # regenerate unit_check_packet.json + variant_*.json
cd ../..
# assert actual vs ground truth (both layers, deterministic, offline, no LLM cost)
uv run pytest test_qa_spine_unit_checks.py test_qa_spine_integration_verdict.py -v
```
