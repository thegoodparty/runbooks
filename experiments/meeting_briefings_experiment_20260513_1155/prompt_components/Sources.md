Citation and source capture rules for every claim in the briefing.

Sources serve three consumers: the UI (provenance display), QA (claim verification), and the chatbot (grounded answers). All three depend on the same source record — the fields below are not optional.

## Capture rules

Capture each source at the moment you fetch it, not at assembly time. `retrieved_at` and `retrieved_text_or_snapshot` must be set when you call `http.get()` or query Databricks — not when you write the artifact.

## Required fields per source

```json
{
  "id": "src-001",
  "name": "Descriptive title of the source document or page",
  "url": "permanent URL — see URL rules below",
  "source_type": "agenda_packet | news | government_website | campaign | haystaq",
  "retrieved_at": "ISO 8601 timestamp set at fetch time",
  "retrieved_text_or_snapshot": "verbatim text captured from the source at retrieval time — required for all source types"
}
```

Additional fields by source type:

- **agenda_packet**: `page_number` (integer or null), `section_heading` (string or null)
- **news**: `article_date` (YYYY-MM-DD or null), `article_type` ("reporting" | "opinion" | "editorial")
- **haystaq**: `haystaq_column` (the `hs_*` column used), `score_value` (the raw mean score), `district_voters_n` (total active voters in district)
- **campaign**: `specific_claim_found` (the exact text from the campaign site that is being cited)

## `retrieved_text_or_snapshot` requirements

- **Agenda packet**: the verbatim extracted text of the relevant section(s), not the full document. Include enough surrounding context for a QA reader to verify the claim without re-fetching.
- **News articles**: the article body text captured via `http.get()`. If the page is paywalled or returns no usable body, note that and do not cite the article.
- **Government websites**: the relevant paragraph(s) from the page body.
- **Haystaq**: a structured summary of the query result — column name, mean score, district filter used, total voters in denominator.
- **Campaign**: the verbatim passage from the campaign site.

Do not truncate to a single sentence. A QA reader must be able to verify the claim solely from `retrieved_text_or_snapshot` without re-fetching the URL.

## URL rules

- Use the permanent, stable URL for every source — not a presigned S3 URL, not a redirect.
- For the agenda packet: use the value of `agendaPacketUrl` from PARAMS as the permanent URL. Never use the presigned fetch URL — it expires within hours.
- For Haystaq data: set `url` to `null`. There is no public URL for modeled constituent data.

## Allowed sources

- Agenda packet and accompanying staff reports for the upcoming meeting
- Local government website for the jurisdiction
- Local news outlets (see `recent_news.md` for credibility guidance)
- Campaign website for the elected official (contextual only)
- Databricks Haystaq L2 modeled scores

## Per-claim citation requirements

Every factual claim in the briefing must reference at least one source. For each claim:
- `source_extracts[]` — verbatim passages from the source that support the claim. Must be extractable from `retrieved_text_or_snapshot`.
- `source_ids[]` — references to `id` values in the sources array.
- `required_source_type` — the minimum acceptable source type for this claim to be released. See routing table below.
- `route_if_unsupported` — what to do if no source of the required type can be found.

## Source routing table

| Claim type | Required source type | Route if unsupported |
|---|---|---|
| Dollar amounts, vote counts, contract figures | `agenda_packet` or `government_website` | `block_release` |
| Legal citations, ordinance text | `agenda_packet` | `block_release` |
| Staff recommendations | `agenda_packet` | `block_release` |
| Constituent sentiment figures | `haystaq` | `block_release` |
| News context, background | `news` | `omit_claim` |
| Historical context | `news` or `government_website` | `omit_claim` |
| Inferred or synthesized observations | none — label as inferred | `flag_as_inferred` |
