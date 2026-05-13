Produce a briefing for the elected official's next city council meeting given your role defined in `about_the_agent.md`.

## Inputs

- Official name and jurisdiction
- Meeting date
- Agenda packet (PDF)

## Briefing structure

**Header:** Official name, estimated read time

**Agenda:** Numbered list of all items, priority items bolded

**Executive Summary:** "The following items on your agenda require action and/or have a vote:" followed by one line per priority item -- what it requires (vote / no vote) and what's at stake

**Priority items** (see `agenda_items.md` for selection criteria):
- Overview *(always)*
- Constituent Sentiment -- `constituent_sentiment.md` *(conditional: report constituent sentiment only if a relevant Haystaq score exists, always invite to run a poll or survey on that issue)*
- Recent News -- `recent_news.md` *(conditional: only if recent local coverage exists)*
- Budget Impact -- `budget_impact.md` *(conditional: only if figures are available)*
- Key Observations -- `talking_points.md` *(always)*
- Sources -- `Sources.md` *(always)*

**Non-priority items:** One sentence each. See `agenda_items.md`.

## Required disclosure

## Output artifacts

See `output_artifacts.md`.