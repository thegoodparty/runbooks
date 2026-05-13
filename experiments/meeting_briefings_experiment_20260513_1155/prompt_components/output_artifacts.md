The meeting briefing produces four output artifacts.

## briefing.json

Structured briefing content. One object per priority item containing all populated sections (overview, constituent sentiment, constituent quote, recent news, budget impact, talking points). Non-priority items included as a flat array of one-sentence descriptions.

## claims.json

A flat list of every factual claim in the briefing. Each entry includes:
- `claim_text` - Verbatim text which appears in the briefing. 
- `claim_type` - Could be a budget number, constituent sentiment, meeting name, meeting date 
- `claim_weight` -- high / medium / low
- `source_extracts[]` -- verbatim passages from the cited sources
- `source_ids[]` -- references to entries in sources.json
- `source_type` -- - Official budget, Agenda PDF, Staff report, Haystaq constituent data, News, campaign website, etc.

## sources.json

The full bibliography. Each entry includes source name, URL, type (agenda_packet / news / campaign / haystaq / government_website), date accessed, and any location metadata (page numbers for PDFs, article date for news).
 