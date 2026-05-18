#!/usr/bin/env python3
"""Render a meeting_briefing artifact JSON into a PM-facing markdown view.

Drops audit fields (claims, sources snapshots, run_decisions, required_data_points,
raw_context, research) so the rendered output matches what an EO would see in the
UI. The full JSON remains intact for QA / chatbot / UI consumers.

Usage:
    python3 render_briefing.py artifact.json [out.md]

If out.md is omitted, prints to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BRIEFING_TYPE_LABELS = {
    "city_council_meeting": "City Council",
    "county_legislature_meeting": "County Legislature",
    "school_board_meeting": "School Board",
}

OFFICIAL_ROLE_LABELS = {
    "city_council_meeting": "City Council Member",
    "county_legislature_meeting": "County Legislator",
    "school_board_meeting": "School Board Member",
}

STATUS_EXPLANATIONS = {
    "awaiting_agenda": "The agenda has not been published yet. Check back closer to the meeting date.",
    "no_meeting_found": "No upcoming meeting was found within the search window.",
    "agenda_provided_by_user": "Briefing generated against a user-supplied agenda.",
    "error": "An error occurred during briefing generation.",
}


def render(artifact: dict[str, Any]) -> str:
    lines: list[str] = []

    briefing_type = artifact.get("briefing_type", "")
    briefing_label = BRIEFING_TYPE_LABELS.get(briefing_type, briefing_type or "Meeting")
    role_label = OFFICIAL_ROLE_LABELS.get(briefing_type, "")
    official = artifact.get("official_name", "").strip()
    meeting_date = artifact.get("meeting_date", "").strip()
    meeting_name = (artifact.get("meeting_name") or briefing_label).strip()
    location = (artifact.get("location") or "").strip()

    lines.append(f"# Meeting Briefing — {meeting_name}")
    lines.append("")
    prepared_for = f"**Prepared for {role_label} {official}**".strip()
    if prepared_for != "**Prepared for**":
        lines.append(prepared_for)
    meeting_line = " · ".join(part for part in (meeting_date, location) if part)
    if meeting_line:
        lines.append(meeting_line)
    lines.append("")

    status = artifact.get("briefing_status", "briefing_ready")
    if status not in ("briefing_ready", "agenda_provided_by_user"):
        lines.append("---")
        lines.append("")
        lines.append(f"## Briefing status: `{status}`")
        lines.append("")
        lines.append(STATUS_EXPLANATIONS.get(status, status))
        lines.append("")
        _append_disclosure(lines, artifact)
        return "\n".join(lines).rstrip() + "\n"

    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    exec_summary = (artifact.get("executive_summary") or "").strip()
    if exec_summary:
        lines.append(exec_summary)
        lines.append("")

    items = artifact.get("items") or []
    featured = [item for item in items if item.get("tier") == "featured"]
    queued = [item for item in items if item.get("tier") == "queued"]

    for idx, item in enumerate(featured, start=1):
        lines.append("---")
        lines.append("")
        _render_featured_item(lines, item, idx)

    if queued:
        lines.append("---")
        lines.append("")
        lines.append("## Queued items")
        lines.append("")
        for item in queued:
            _render_queued_item(lines, item)

    if items:
        lines.append("---")
        lines.append("")
        lines.append("## Full Agenda")
        lines.append("")
        lines.append("All items, in order. Featured items are bolded.")
        lines.append("")
        lines.append("| # | Item | Detail |")
        lines.append("|---|---|---|")
        featured_ids = {id(item) for item in featured}
        for j, item in enumerate(items, start=1):
            item_num = item.get("item_number") or str(j)
            title = item.get("title", "")
            if id(item) in featured_ids:
                section_num = featured.index(item) + 1
                lines.append(f"| {item_num} | **{title}** | See Section {section_num} |")
            else:
                lines.append(f"| {item_num} | {title} | |")
        lines.append("")

    _append_disclosure(lines, artifact)
    return "\n".join(lines).rstrip() + "\n"


def _render_featured_item(lines: list[str], item: dict[str, Any], section_num: int) -> None:
    title = item.get("title", "")
    lines.append(f"## {section_num}. {title}")
    lines.append("")
    item_num = item.get("item_number")
    if item_num:
        lines.append(f"*Agenda item {item_num}.*")
        lines.append("")

    display = item.get("display") or {}

    summary = (display.get("summary") or "").strip()
    if summary:
        lines.append("### Overview")
        lines.append("")
        lines.append(summary)
        lines.append("")

    budget = display.get("budget_impact")
    if budget:
        budget_summary = (budget.get("summary") or "").strip()
        if budget_summary:
            lines.append("### Budget impact")
            lines.append("")
            lines.append(budget_summary)
            lines.append("")

    sentiment = display.get("constituent_sentiment")
    if sentiment:
        sentiment_summary = (sentiment.get("summary") or "").strip()
        district_note = (sentiment.get("district_note") or "").strip()
        if sentiment_summary or district_note:
            lines.append("### Constituent sentiment")
            lines.append("")
            if sentiment_summary:
                lines.append(sentiment_summary)
            if district_note:
                if sentiment_summary:
                    lines.append("")
                lines.append(district_note)
            lines.append("")

    quote = display.get("constituent_quote")
    if quote:
        text = (quote.get("text") or "").strip()
        attribution = (quote.get("attribution") or "").strip()
        if text:
            lines.append("### Constituent quote")
            lines.append("")
            lines.append(f"> {text}")
            if attribution:
                lines.append(">")
                lines.append(f"> — {attribution}")
            lines.append("")

    news = display.get("recent_news") or []
    if news:
        lines.append("### Recent news")
        lines.append("")
        for entry in news:
            headline = (entry.get("headline") or "").strip()
            publication = (entry.get("publication") or "").strip()
            url = (entry.get("url") or "").strip()
            if not headline:
                continue
            if url:
                base = f"- [{headline}]({url})"
            else:
                base = f"- {headline}"
            if publication:
                base += f" — *{publication}*"
            lines.append(base)
        lines.append("")

    points = display.get("talking_points") or []
    if points:
        lines.append("### Talking points")
        lines.append("")
        for point in points:
            lines.append(f"- {point}")
        lines.append("")


def _render_queued_item(lines: list[str], item: dict[str, Any]) -> None:
    title = item.get("title", "")
    item_num = item.get("item_number")
    heading = f"### Item {item_num} — {title}" if item_num else f"### {title}"
    lines.append(heading)
    lines.append("")
    display = item.get("display") or {}
    summary = (display.get("summary") or "").strip()
    if summary:
        lines.append(summary)
        lines.append("")
    sentiment = display.get("constituent_sentiment")
    if sentiment:
        sentiment_summary = (sentiment.get("summary") or "").strip()
        if sentiment_summary:
            lines.append(f"*{sentiment_summary}*")
            lines.append("")


def _append_disclosure(lines: list[str], artifact: dict[str, Any]) -> None:
    disclosure = (artifact.get("disclosure") or "").strip()
    if disclosure:
        lines.append("---")
        lines.append("")
        lines.append(f"*{disclosure}*")
        lines.append("")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__, file=sys.stderr)
        return 1
    artifact_path = Path(sys.argv[1])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    markdown = render(artifact)
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
        out_path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
