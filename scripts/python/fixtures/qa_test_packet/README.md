# QA test packet

A realistic agent-assembled clean baseline briefing plus targeted defects, with a ground-truth
manifest that says what the QA spine should conclude for each case. This is reusable test
substrate: deterministic and agentic checks run against it, two automated meta-tests assert the
spine's behavior, and the `fails_not_yet_caught` cases double as the roadmap for checks we still
need.

The baseline is a frozen, committed snapshot: the source S3 runs it was assembled from live only in the gitignored `.reference_docs/` scratch, so it is intentionally not reproducible by others. Treat the committed JSON as the ground truth.

The packet is organized in **two layers** (packet_version 3.0):

- **Layer 1, unit (the primary ask).** A SINGLE unit packet, `unit_check_packet.json`, that
  folds the per-claim / per-item defects into one file, each isolated so that ONLY its intended
  check reacts on its target. The unit meta-test runs the deterministic spine once and asserts
  EACH check's individual result on its target (by `check_id` + `offending`), IGNORING the
  packet's overall `release_verdict`. This verifies that each check function catches what it
  should (and does not fire when it should not) regardless of how the whole briefing routes.
- **Layer 2, integration.** A small set of thin, single-condition fixtures where the whole-artifact
  `release_verdict` is the point: one block-routed defect, one annotate-routed defect, a whole-doc
  identity case, a whole-doc schema case, plus the clean baseline as the ok control. The
  integration meta-test asserts the verdict per fixture.

A green pair of meta-tests means a green run on live briefings is trustworthy: each check
demonstrably fires on its planted defect, demonstrably does NOT fire on its planted false
positive, and the verdict routing demonstrably composes those routes correctly.

## What is here

```
qa_test_packet/
  agent_assembled_baseline.json    realistic clean baseline (verdict OK); integration ok-control
                                   AND the base every other packet-3.0 fixture derives from
  unit_check_packet.json           LAYER 1, baseline + several isolated per-check defects in ONE file
  hybrid_agenda_packet.md          synthetic hybrid agenda packet the baseline was assembled from
  build_variants.py                regenerates unit_check_packet.json and variants/variant_*.json
  variants/
    variant_single_blocking_defect.json   LAYER 2, one block-routed defect    (verdict block)
    variant_single_annotate_defect.json   LAYER 2, one annotate-routed defect (verdict warn)
    variant_identity_missing.json         LAYER 2, blank official_name        (verdict block)
    variant_schema_drift.json             LAYER 2, extra top-level property   (verdict warn)
  qa_test_packet_manifest.json     ground-truth: every case -> layer, module, bucket, rubric
                                   dimension, target check, expected per-check result (unit) OR
                                   expected_release_verdict (integration); + rubric_coverage summary
  provenance_and_ledger.md         source-run provenance, clean-vs-planted ledger, buggy-check findings
  README.md                        this file
```

## The two meta-tests

```bash
# from scripts/python/ (both are deterministic, offline, and incur no LLM cost)
uv run pytest test_qa_spine_unit_checks.py test_qa_spine_integration_verdict.py -v
```

- **`test_qa_spine_unit_checks.py` (Layer 1).** Runs `qa_validate.run_deterministic` ONCE over
  `unit_check_packet.json`, then asserts each check's individual result on its target by
  `check_id` (and `offending`). `release_verdict` is never asserted. Test names map 1:1 to
  targets: `test_extract_not_in_source_is_caught`,
  `test_money_mismatch_is_caught_by_structured_match`,
  `test_budget_cited_to_news_is_caught_by_source_hierarchy`,
  `test_advocacy_in_authored_prose_is_flagged`,
  `test_advocacy_inside_quoted_source_is_not_flagged`, `test_truncated_extract_is_not_flagged`,
  `test_paraphrased_summary_is_diagnostic_only`.
- **`test_qa_spine_integration_verdict.py` (Layer 2).** Computes `compute_release_verdict` per
  fixture and asserts it: `test_clean_baseline_routes_ok`,
  `test_single_blocking_defect_routes_block`, `test_single_annotate_defect_routes_warn`,
  `test_identity_missing_routes_block`, `test_schema_drift_routes_warn`.

Every expectation was calibrated by ACTUALLY RUNNING the validator (never hand-guessed). A
failure means the spine's behavior drifted from ground truth, so re-calibrate or fix the regression.
LLM-dependent cases are documented in the manifest (`requires_llm` / `expected_llm`) but never
auto-asserted; neither test calls a paid LLM.

## The unit packet's targeted cases

Each target uses a DISTINCT claim / item / source so several coexist in one file without colliding;
literal consistency is preserved everywhere else so only the intended check reacts.

| Target | Check | Expected result | Kind |
|---|---|---|---|
| claim_008 extract absent from cited source | `extracts_appear_in_cited_source` | fail / block | caught defect |
| claim_004 invented $45M figure | `high_stakes_structured_match` | fail / block | caught defect |
| claim_005 budget_number cited to NEWS-1 | `source_hierarchy_policy` | fail / block | caught defect |
| item_001 'Push for' in authored summary | `prohibited_phrases` | warning / annotate | caught defect |
| claim_009 true-but-truncated extract | `extracts_appear_in_cited_source`, `high_stakes_structured_match` | pass (no fail on claim_009) | false positive |
| NEWS-2 / claim_010 'demand' inside a quoted source | `prohibited_phrases` | does NOT fire (no 'demand' in any finding) | false positive |
| item_005 / item_010 faithful paraphrase | `summary_source_coherence` | warning / **diagnostic** (never block) | false positive |

The unit packet's overall verdict happens to be `block` (because three block-routed checks fire),
but that is irrelevant to the unit assertions and is recorded only for completeness.

## The integration fixtures

| Fixture | Condition | Expected verdict |
|---|---|---|
| `agent_assembled_baseline.json` | clean | **ok** |
| `variants/variant_single_blocking_defect.json` | one block-routed defect (claim_008 extract miss) | **block** |
| `variants/variant_single_annotate_defect.json` | one annotate-routed defect ('Push for') | **warn** |
| `variants/variant_identity_missing.json` | whole-doc identity (blank official_name) | **block** |
| `variants/variant_schema_drift.json` | whole-doc schema (extra top-level property) | **warn** |

## Agent assembly (how the clean baseline was born)

`agent_assembled_baseline.json` is a genuine `briefing_ready` artifact assembled by a
clean-context sub-agent that followed the offline meeting_briefing assembly brief over the
synthetic `hybrid_agenda_packet.md`. Generation is non-deterministic, so it is snapshotted once.
It carries the full enriched `briefing_ready` shape: 15 items, 16 claims, 13 sources spanning
`agenda_packet` / `news` / `haystaq`. `unit_check_packet.json` and every `variant_single_*` /
`variant_identity_missing` / `variant_schema_drift` file derive from it (regenerate with
`uv run python build_variants.py`). See `provenance_and_ledger.md` for which real S3 runs
contributed which agenda forms.

## Rubric coverage

Coverage of what to plant is driven by the Meeting Briefing QA Rubric: 5 scored dimensions
(Accuracy, Grounding & Traceability, Prioritization, Coverage, Actionability) and 4 gating checks
(no political advocacy, no toxic/discriminatory, no inappropriate PII, professional register).
Every defect case carries a `rubric_dimension`, and the manifest's top-level `rubric_coverage`
object maps each dimension to `covered` (a deterministic check fires) or `gap` (roadmap,
`fails_not_yet_caught` with a `proposed_check`). Today: Accuracy, Grounding, and the
advocacy gate are covered by fixtures in this packet; Prioritization, Actionability, and the
toxic / PII / register gates are gaps. Coverage is covered by the spine (`claim_coverage`,
`completeness_floor`) but no longer exercised by a fixture here (its cases lived on the orphaned
packet-1.0 layer, dropped in 3.1). The roadmap-gap cases have NO check function to unit-test, so they are kept as
documentation-only `proposed_check` entries (their standalone variant files were removed in the
packet-3.0 refactor).

The artifact conforms to `experiments/meeting_briefing/manifest.json#output_schema`
(MeetingBriefingFull). "Both sides" of QA live in one file: the source agenda packet and supporting
documents are the `sources[].retrieved_text_or_snapshot` text; the generated briefing is
`executive_summary` + `items[]` + `claims[]`. Seeded defects live in the briefing and trace back
to specific sources.

## Three buckets per module

- **passes_today**: correct/healthy, or a planted false positive the spine must not block.
- **fails_caught**: a defect today's spine surfaces (block, annotate, or diagnostic).
- **fails_not_yet_caught**: a defect no current check surfaces. The manifest's `proposed_check`
  names the check that should exist. This is the roadmap.

## Running a single artifact against the spine

From `scripts/python/`:

```bash
# Deterministic only, offline (no network, no LLM cost); the calibration path
uv run python qa_validate.py fixtures/qa_test_packet/unit_check_packet.json --no-llm --no-check-urls
uv run python qa_validate.py fixtures/qa_test_packet/agent_assembled_baseline.json --no-llm --no-check-urls
uv run python qa_validate.py fixtures/qa_test_packet/variants/variant_single_blocking_defect.json --no-llm --no-check-urls
```

Each run writes a `qa_bundle.json` next to the artifact (or use `--bundle-out PATH`). Compare its
`deterministic_checks[]` and `release_verdict` against the matching cases in the manifest.

## Provenance and safety

Structure and source prose are adapted from the example briefings in `.reference_docs/mb_runs/`.
The jurisdiction (Lakemont / Riverton), the official (Jordan Avery / Maya Chen), and every seeded
defect are fictional and synthetic. No real council, person, or record is the subject of a planted
defect.

## Maintenance

Calibrated against runbooks `develop`, product spec `1.3-ws2`. The unit packet and thin integration
variants were calibrated 2026-06-08. If the spine's checks or thresholds change, regenerate with
`uv run python build_variants.py`, re-run the deterministic commands above, and reconcile the
manifest's `expected_deterministic` / `expected_release_verdict` entries.
