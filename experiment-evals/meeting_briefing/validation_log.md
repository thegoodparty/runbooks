# meeting_briefing rubric — validation log (cold run 20260605-101359)

Reliability tuning. Cold judges read ONLY rubric.md + one artifact. Full judge blocks in `judges/<uuid>.<A|B>.md`. Held-out batches (heldout1/2/3) are reserved random draws, never used in tuning.

## Population note (drives the whole design)
Random sample of 121 landed prod artifacts: **100 `awaiting_agenda`, 10 `briefing_ready`, 10 `no_meeting_found`, 1 `error`.** 83% are precondition-unmet placeholders. Implication: the eligibility gate fires on the large majority; the rare full briefing is what the scored scale must rank. Synthesis tuning set was enriched with the 7 spare `briefing_ready` (allowed — synthesis may be curated); held-out batches left as pure random draws (mostly DQ, faithful to the real population).

---

## Iteration 1 — rubric v1, synthesis tuning set (5 artifacts, 2 judges each)

| uuid (city) | A | B | spread | result |
|---|---|---|---|---|
| 019e7340 (Rochester, reader-best) | 28 | 29 | 1 | PASS both |
| 019e72f6-bd10 (Acworth, reader-worst) | DQ-faith | DQ-faith | 0 | **Gate B fired on both** |
| 019e73ae-be8f (Northumberland) | 28 | 27 | 1 | PASS both |
| 019e7228 (NYC CEC4 / Homestead-positioned) | 25 | 22 | **3** | PASS both, spread 3 |
| 019e7389-a786 (awaiting_agenda placeholder) | DQ-elig | DQ-elig | 0 | **Gate A fired on both** |

**Diagnosis.** Gates are reproducible on both anchors (fatal-grounding DQ on Acworth; eligibility DQ on placeholder) — the worked-example "cap cliff" trap is avoided because borderline-grounding is gated, not scored. The single spread>2 is 019e7228, and it is NOT one anchor read two ways — it is three dimensions each off by exactly 1, all at the same fuzzy boundary:
- D2 talking-points 4 vs 3 — judge B docked for hedged "you may want to ask" bullets + missing `## Posture override`; A held at 4.
- D3 sentiment 5 vs 4 — judge B docked because a *citywide* Haystaq figure (4,286,425 voters) is labeled "district" without flagging it is NYC-SD-wide, not CEC District 4; A did not penalize.
- D4 tiering 5 vs 4 — judge B treated featuring a no-vote presentation as "one borderline call" → 4; A rolled it into 5.

Root cause = the **5↔4 boundary is under-specified** on the count-based dims: "minor slip" / "one borderline call" / "several hedges" are left to the judge. This accumulates ±1 errors into a spread of 3.

**Change driven (the one change):** make the 5↔4 (and 4↔3) boundaries on D2, D3, D4 concrete and count-based — name exactly what costs a point (a scope-label mismatch; a borderline tier placement; a hedged/restatement bullet) so two judges resolve the boundary identically. → rubric.v2.

---

## Iteration 2 — rubric v2, widened synthesis set (all 8 full briefings, 2 judges each)

Judge files: `judges/<uuid>.v2.<A|B>.md`.

| uuid (city) | A | B | spread | result |
|---|---|---|---|---|
| 019e7340 (Rochester) | 29 | 30 | 1 | PASS both |
| 019e72f6-bd10 (Acworth) | DQ-faith | DQ-faith | — | **Gate B both** (smell test + self-admission cited) |
| 019e72f6-bf78 (Menomonie) | 28 | 29 | 1 | PASS both |
| 019e73ae-be8f (Northumberland) | 28 | 26 | 2 | PASS both |
| 019e7228 (NYC CEC4) | 26 | 26 | **0** | PASS both (was spread 3 under v1) |
| 019e732d (Homestead) | 29 | 28 | 1 | PASS both |
| 019e739c (Le Mars) | 30 | 30 | 0 | PASS both |
| 019e73c0 (Brookline) | 28 | 26 | 2 | PASS both |

**Result.** Graded spreads {1,1,2,0,1,0,2}: max=2, mean≈1.0, zero blowouts, both gates reproducible across all 8. The v1 spread-3 case (019e7228) collapsed to 0 — the count-based D2/D3/D4 anchors removed the accumulating ±1 judgment differences. Residual spread-2s (Northumberland, Brookline) are D2 weak-bullet counting and D3 defect counting (one judge counts a disclosed-but-stretched proxy as a defect, the other doesn't) — genuine ±1 calls within threshold, not a structural ambiguity worth a cliff.

**Decision:** spread is small and stable (max 2 ≤ verdict threshold, mean ~1). Per Step 4 "stop when the spread is small and stable." **Lock v2 as the candidate**; do NOT chase the two residual spread-2s (over-tuning risk + they are taste-level ±1). Proceed to Step 5 held-out validation, which is the real test.

---

## Step 5 — Held-out validation (rubric v2, locked; never tuned against held-out)

**Held-out batching note (deviation, justified).** The runbook assumes a gradeable-majority population. meeting_briefing is the inverse: ~83% of artifacts are `awaiting_agenda` placeholders, so a *purely random* held-out batch of 10 yields ~0-2 graded briefings — too thin to measure scoring reliability. Resolution:
- `heldout1` / `heldout2` / `heldout3` — pure random draws (faithful to the real population, dominated by the gate). Used to test **gate reproducibility** on unseen placeholders.
- `heldout_graded` — a **fresh stratified draw**: random shuf positions 211-470 (never pulled, never tuned on), filtered to `briefing_ready`, first 10 taken. Random *within the graded stratum*, not hand-picked. Used to measure **graded inter-judge spread** on unseen briefings. This is disclosed, not curated by quality.

### heldout_graded (10 fresh, unseen briefing_ready), 2 judges each — judges/<uuid>.<A|B>.md
| uuid | A | B | spread |
|---|---|---|---|
| 019e7228-5e9c | 29 | 27 | 2 |
| 019e729a-cbef | 26 | 26 | 0 |
| 019e729a-cde8 | 28 | 28 | 0 |
| 019e72bf-869b | 27 | 27 | 0 |
| 019e72bf-8ef4 | 28 | 29 | 1 |
| 019e72bf-99cf | 25 | 26 | 1 |
| 019e72d1-f3b8 | 27 | 28 | 1 |
| 019e72f6-ab8c | 28 | 27 | 1 |
| 019e732d-ceab | 30 | 30 | 0 |
| 019e732d-cee7 | 28 | 27 | 1 |

Max spread 2, mean 0.7, **zero blowouts**. The cliff-→-blowout failure the runbook warns about (the meeting_briefing "cap cliff") did NOT occur — because the borderline-grounding population is handled by **Gate B (DQ)**, not by a low substance score. No held-out batch informed a change → no batch consumed.

### heldout1 (10 random, all awaiting_agenda) — gate reproducibility on unseen placeholders
All 10 → **DQ-eligibility on BOTH judges. Zero splits.**

### heldout2 (random: 7 awaiting_agenda + 1 no_meeting_found + 2 briefing_ready)
- 8 placeholders (incl. the `no_meeting_found` branch) → **DQ-eligibility on both judges, zero splits.**
- 019e73ae-727b (briefing_ready) → 28 / 30 (spread 2)
- 019e73ae-ce9b (briefing_ready) → 28 / 29 (spread 1)

No structural failure anywhere → **no v3 needed.** All three held-out batches are unspent (none informed a change), so all are valid verdict data (Step 6: combine untouched batches). `heldout3` held in reserve, unused.

## Step 6 — Verdict

`scores.tsv` = unspent held-out batches (heldout1 + heldout2 + heldout_graded) = 30 artifacts, 12 graded + 18 DQ. `scripts/python/rubric_verdict.py` → **`verdict.txt`**:

```
briefings scored: 30 | graded 12 | disqualified (unanim) 18 | gate SPLIT 0
graded inter-judge spread: max=2  mean=0.83 | blowouts(>=5): 0 | graded range 25-30
[PASS] gate decisions reproducible (no 1-of-2 split)
[PASS] max graded spread <= 2
[PASS] zero blowouts (>= 5)
VERDICT: GO — reliable enough to gate prompt changes
```

**Final rubric: `rubric.md` (= rubric.v2.md). Two tuning iterations. Held-out spread max 2 / mean 0.83. Verdict: GO.**

Reliability only — validity vs. human truth is NOT established (see runbook "What this does NOT give you"). The taste-level dimensions here are D2 (talking-point actionability) and D6 (concision); a one-time human calibration pass against a held-out set would raise validity confidence.
