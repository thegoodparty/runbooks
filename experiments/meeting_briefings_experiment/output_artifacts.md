The meeting briefing produces four output artifacts.

## briefing.json

Structured briefing content. One object per priority item containing all populated sections (overview, constituent sentiment, constituent quote, recent news, budget impact, talking points). Non-priority items included as a flat array of one-sentence descriptions.

## claims.json

A flat list of every factual claim in the briefing. Each entry includes:
- `claim_text`
- `claim_weight` -- high / medium / low
- `source_extracts[]` -- verbatim passages from the cited source
- `source_ids[]` -- references to entries in sources.json

Used by the QA layer to verify that claims are backed by their stated sources.

## sources.json

The full bibliography. Each entry includes source name, URL, type (agenda_packet / news / campaign / haystaq / government_website), date accessed, and any location metadata (page numbers for PDFs, article date for news).

## source_snapshots/

One text file per source, named by source_id. Contains the verbatim content extracted from the source document. Used by the QA layer for inline verification.
