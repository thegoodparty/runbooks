The meeting briefing pipeline writes a single JSON artifact. It has four top-level keys: `run_metadata`, `briefing`, `claims`, and `sources`.

The UI consumes `briefing`. QA consumes `claims` and `sources`. The chatbot consumes `briefing` plus `sources[*].retrieved_text_or_snapshot`. The `claims` and `sources` arrays are stripped from the display API response before the official sees them.

## `run_metadata`

Captured once at the start of the run.

```json
{
  "experiment_id": "meeting_briefings_experiment_...",
  "briefing_version": "the instruction.md version tag, e.g. v2",
  "agenda_packet_url": "the permanent agendaPacketUrl value from PARAMS",
  "generated_at": "ISO 8601 UTC timestamp",
  "source_bundle_retrieved_at": "ISO 8601 UTC timestamp set when the last source was fetched"
}
```

`agenda_packet_url` must be the value of `agendaPacketUrl` from PARAMS — the stable, permanent URL. Never use a presigned fetch URL here.

## `briefing`

Structured briefing content for the UI. One object per priority item. Non-priority items as a flat array of one-sentence descriptions.

```json
{
  "official_name": "...",
  "meeting_date": "YYYY-MM-DD",
  "estimated_read_time_minutes": 8,
  "required_disclosure": "This briefing was generated with AI assistance and may contain errors. Inferred or synthesized content represents model-generated interpretation, not verified fact. Constituent sentiment data, where present, reflects modeled estimates for constituents in that jurisdiction.",
  "agenda": [
    {"item_number": "5F", "title": "...", "is_priority": true}
  ],
  "executive_summary": "The following items on your agenda require action and/or have a vote:",
  "action_items": [
    {
      "item_number": "5F",
      "title": "...",
      "requires_vote": true,
      "overview": "What is actually at stake — not just what the item is.",
      "constituent_sentiment": {
        "summary": "**72% support · 28% oppose**",
        "detail": "One sentence describing what the score means for this jurisdiction as a modeled estimate.",
        "haystaq_column": "hs_infrastructure_funding_fund_more"
      },
      "recent_news": [
        {
          "title": "Headline text",
          "outlet": "Publication Name",
          "article_type": "reporting | opinion | editorial",
          "publication_date": "YYYY-MM-DD",
          "url": "permanent article URL"
        }
      ],
      "budget_impact": {
        "summary": "Plain-language summary of cost figures extracted verbatim from source.",
        "figures": [
          {"label": "Total contract", "value": "$2,179,995.83", "source_id": "src-001"}
        ]
      },
      "talking_points": [
        "One or two sentence observation."
      ],
      "sources": [
        {
          "id": "src-001",
          "label": "City Council Agenda — April 16, 2026",
          "kind": "agenda_packet | news | government_website | campaign | haystaq",
          "url": "permanent URL or null for haystaq"
        }
      ]
    }
  ],
  "non_priority_items": [
    {"item_number": "1", "title": "Call to Order", "description": "One sentence."}
  ]
}
```

`constituent_sentiment` is `null` if no relevant Haystaq column exists for the item.
`recent_news` is `null` if no recent local coverage exists.
`budget_impact` is `null` if no figures are available in source documents.

## `claims`

A flat list of every factual claim in the briefing. Used by QA to verify that each claim is supported before release.

```json
[
  {
    "claim_id": "claim_001",
    "section": "budget_impact | constituent_sentiment | recent_news | overview | talking_points",
    "item_title": "title of the priority item this claim appears in",
    "claim_text": "Verbatim text as it appears in the briefing.",
    "claim_type": "budget_number | vote_count | legal_citation | staff_recommendation | constituent_sentiment | news_context | historical_context | inferred",
    "claim_weight": "high | medium | low",
    "source_extracts": ["verbatim passage from the source that supports this claim"],
    "source_ids": ["src-001"],
    "required_source_type": "agenda_packet | government_website | news | haystaq | none",
    "route_if_unsupported": "block_release | omit_claim | flag_as_inferred"
  }
]
```

See `Sources.md` for the routing table mapping claim type to `required_source_type` and `route_if_unsupported`.

`claim_weight` guidance:
- `high` — dollar amounts, vote counts, legal text, names, dates: must be verbatim from source
- `medium` — operational data, policy context, procedural facts
- `low` — historical context, background

## `sources`

Full bibliography. Each entry must include the text captured at retrieval time. See `Sources.md` for the complete field specification.

The critical field is `retrieved_text_or_snapshot` — set at fetch time, not at assembly. The QA layer and chatbot both depend on this field. Do not omit it or set it to null.

```json
[
  {
    "id": "src-001",
    "name": "City of Alvin City Council Agenda — April 16, 2026",
    "url": "permanent URL — use agendaPacketUrl from PARAMS for the agenda, never the presigned fetch URL",
    "source_type": "agenda_packet",
    "retrieved_at": "ISO 8601 timestamp set at fetch time",
    "retrieved_text_or_snapshot": "verbatim text from the source captured at retrieval time",
    "page_number": null,
    "section_heading": null,
    "article_date": null,
    "article_type": null
  }
]
```

## Chatbot context

The chatbot has access to the full artifact. It uses:
- `briefing` — the structured briefing to answer questions about the meeting
- `sources[*].retrieved_text_or_snapshot` — the raw source text for grounded, citable answers
- `run_metadata.agenda_packet_url` — stable link to the agenda PDF

The chatbot does not need `claims` — that is a QA artifact.

## What the display API strips

Before serving to the UI, gp-api removes `claims` from the response. The `sources` array is kept but `retrieved_text_or_snapshot` is stripped (too large for the display payload). The `briefing.action_items[*].sources` embedded list is what the UI renders for provenance.
