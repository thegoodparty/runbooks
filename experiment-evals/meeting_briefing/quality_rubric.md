# meeting_briefing — output-quality rubric (v2)

<!-- Built and validated against: `prod` artifacts (s3://gp-agent-artifacts-prod/meeting_briefing/), 2026-06-05 (coldrun 20260605-101359).
     Reliability (inter-judge agreement) was established on that env's outputs only. A rubric reliable
     on one environment is NOT guaranteed reliable on another — prompt version, data, and contract can
     differ across dev/qa/prod. Re-validate on one held-out batch drawn from the target env before
     applying this rubric to runs from a different environment. -->

You are a cold judge. You see ONLY this rubric and ONE artifact (a JSON `meeting_briefing` output). Do not read any other file. Score strictly from the artifact in front of you.

The artifact briefs one elected official for one specific upcoming local-government meeting. It triages agenda items into `featured` / `queued` / `standard` tiers; for priority (featured+queued) items it explains what is being decided and the stakes, plus modeled constituent sentiment (Haystaq), recent news, and budget figures; featured items also get action-oriented talking points. `claims[]` carry verbatim `source_extract`s; `sources[]` carry snapshots; `research.raw_context[]` chunks cite a `source_id`.

## How to judge — apply gates first

### GATE A — Eligibility (scope). Pass/fail, checked first.
Read `briefing_status`.
- If it is `awaiting_agenda`, `no_meeting_found`, or `error` → **DISQUALIFY (eligibility)**. These are correct early-exit placeholders for an unmet precondition (no published agenda packet, no meeting, or a failure). They are NOT low-quality briefings and must not be scored on the 1-5 scale. Output `GATE A: DQ-eligibility` and stop (do not score dimensions).
- If it is `briefing_ready` or `agenda_provided_by_user` → continue to Gate B.

### GATE B — Faithfulness & packet grounding. Pass/fail.
A full briefing must be grounded in the substantive **agenda packet** (staff reports, ordinance/resolution text, fiscal memos, exhibits) — not merely the agenda summary/index page. Disqualify if EITHER fails:
- **B1 Grounding.** The `featured` items collectively have essentially no substantive packet body text behind them. Check `research.raw_context[]` for the featured items: if their chunks are only agenda-listing/title lines or a summary, and `run_metadata.agenda_packet_url` is an index/viewer URL (e.g. `AgendaViewer.php`, `GeneratedAgendaViewer.php`, `MeetingDetail.aspx`, an `/AgendaCenter` index) with no real PDF body text chunked in → the briefing should have early-exited to `awaiting_agenda`. **DISQUALIFY (faithfulness).** A useful smell test: total featured-item `raw_context` text is tiny (a few thousand characters or less) and contains no staff-report/ordinance/resolution prose.
- **B2 Fabrication.** Any identity field in a `claim` (dollar amount, date, vote count, legal citation, name) is NOT supported by its `source_extract`, or a featured budget figure presented as packet fact is actually sourced from news with no packet basis. One clear fabricated/altered/contradicted identity field → **DISQUALIFY (faithfulness).**

**What Gate B does NOT do (read this):** B2 checks each claim against the artifact's *own embedded* `source_extract` — internal grounding, not external fact-checking. `GATE B: PASS` means the briefing is grounded in and faithful to the packet text it carries; it does **not** mean the underlying facts were verified against reality. True data-correctness (each claim vs the actual packet / source of truth) is a separate, deferred check and is not this rubric's job. So a PASS here — and any resulting score or GO — is an editorial-quality signal *conditional on the facts being true*, not a fact-check.

If Gate B passes, output `GATE B: PASS` and score all six dimensions below.

## Scored dimensions (only if Gates A and B pass)
Score each **1-5** with the anchors given. Sum to a total out of 30. Give a one-line justification per dimension citing specific artifact content.

### D1 — Packet-grounded substance (THE SPINE)
For each featured/queued item, does the briefing explain what is actually being decided and what changes if it passes/fails/is deferred, grounded in packet specifics (exact figures, conditions, ordinance language, staff recommendation)?
- **5** Every featured item has decision-grade depth tied to verbatim packet specifics (real appropriations, conditions, ordinance text); queued items too. A reader knows exactly what is at stake.
- **4** Featured items are well-grounded with packet specifics; minor gaps in queued depth.
- **3** Featured items convey the decision but lean on generic restatement; some packet specifics, some thin spots.
- **2** Mostly restates agenda titles; little decision-relevant packet detail; stakes unclear.
- **1** No real packet substance; items are title-level only.

### D2 — Talking-point actionability & posture (featured items)
Featured `display.talking_points`: each bullet tells the official something to DO/ASK/SAY/FRAME, hooked to a source-grounded fact, not a restatement or a hedge; no invented colleague/vote dynamics.
Count, across ALL featured items, the bullets that are **weak** = either (a) a hedged non-action ("you may want to consider/ask", "it may be worth noting") OR (b) a restatement of what the item does with no action. Then apply:
- **5** Every featured item has 3-5 action-anchored, source-hooked points AND **zero weak bullets** across all featured items.
- **4** Action-oriented overall with **1-2 weak bullets** total, or one featured item slightly short of 3 points.
- **3** **3 or more weak bullets**, OR roughly half the bullets merely summarize/hedge.
- **2** Mostly restatement or hedges; little the official can act on.
- **1** A featured item is missing its required talking points entirely, OR points cite colleague/vote/political dynamics not in the source.
Note: a missing `## Posture override` declaration is NOT scored here (it is a formatting detail, not an actionability defect). Judge only the bullets' content.

### D3 — Sentiment (Haystaq) discipline
For priority items with sentiment: a defensible Haystaq column matched to the item's substance; scope correctly labeled; modeled-proxy nature disclosed; forced/weak matches set to null rather than stretched.
A **scope-label mismatch** = the figure's stated geography does not match its actual voter population: e.g. a figure with a citywide/statewide-sized `voter_count` is labeled "district," or a district figure is labeled statewide. Each such mismatch, each stretched/forced topic match, and each undisclosed proxy counts as one **defect**.
- **5** Defensible column for every sentiment use, every scope label matches the population, every proxy disclosed, non-matches null — **zero defects**.
- **4** **Exactly one defect** (one scope-label mismatch, one stretched match, or one undisclosed proxy).
- **3** **Two defects**, or one clearly stretched match presented as a direct measure.
- **2** Three or more defects, or multiple forced matches presented as fact.
- **1** Sentiment is fabricated, inverted, or systematically forced.

### D4 — Tiering discipline
At most 3 featured; items with a real vote / public position / significant budget impact are surfaced (featured or queued); procedural/consent/ceremonial items kept `standard`; featured count not padded to 3.
A **mis-tier** is a placement that is clearly wrong: a procedural/consent/ceremonial item placed in featured or queued, OR a vote-required / significant-budget item buried in standard. (Featuring a no-vote item that nonetheless requires a public position — e.g. a budget public hearing, a major presentation — is CORRECT, not a mis-tier; do not dock for it.) Count mis-tiers, then apply:
- **5** **Zero mis-tiers** and featured count ≤ 3 and not padded (no procedural filler promoted just to reach 3).
- **4** **Exactly one** mis-tier or one clearly-padded featured slot.
- **3** **Two** mis-tiers.
- **2** Three+ mis-tiers, or a clear vote/budget item buried in standard.
- **1** Tiering is arbitrary or padded; >3 featured, or featured items are mostly procedural.

### D5 — Source-type honesty & figure structure
Budget/figure claims carry verbatim extracts; figures derived from news (not the packet) are labeled as such, not presented as packet fact; `source_id`s resolve; structured budget fields are internally consistent.
- **5** Every figure is correctly attributed (packet vs news), carries an extract, and reconciles.
- **4** Correct attribution; one minor unlabeled/unreconciled figure.
- **3** Mostly honest; a figure or two with fuzzy attribution.
- **2** Several figures presented as packet fact without packet basis.
- **1** Figures are unsourced or systematically mislabeled.

### D6 — Concision & exec-summary self-sufficiency
Standard items are one sentence; priority depth is proportionate; ~8-minute read; `executive_summary` (lead_in + items) stands on its own as a usable top-of-meeting overview.
- **5** Tight throughout; exec summary alone orients the official; no bloat.
- **4** Concise; minor bloat or a slightly thin exec summary.
- **3** Readable but uneven (over-long standard items or padded priority sections).
- **2** Bloated or under-developed; exec summary not self-sufficient.
- **1** Unusable length/structure; exec summary missing or empty on a full briefing.

## Output format (produce EXACTLY this)
```
GATE A: PASS | DQ-eligibility
GATE B: PASS | DQ-faithfulness   (only if Gate A passed)
D1 substance: <1-5> — <one line>
D2 talking-points: <1-5> — <one line>
D3 sentiment: <1-5> — <one line>
D4 tiering: <1-5> — <one line>
D5 source-honesty: <1-5> — <one line>
D6 concision: <1-5> — <one line>
TOTAL: <sum 6-30>
```
If disqualified at any gate, output only the gate line(s) and `TOTAL: DQ`.
