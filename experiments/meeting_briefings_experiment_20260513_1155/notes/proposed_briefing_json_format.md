Briefing JSON format

Contract for a single briefing payload returned by gp-api to the briefings UI. This is what the briefing-generation pipeline produces and what gp-api stores and serves.

Scope of v1

Only the "Briefing ready" state is in scope. The payload below describes a complete, finished briefing ready for the user to read. "Awaiting agenda" and past briefings have separate, simpler shapes (out of scope for this doc).

The Constituent Quote section has been removed from the design. There is no field for it in this schema.

Top-level shape

{
  "id": "01HQX7K9P1AE3Z3GZB1T5V8M9R",
  "slug": "city-council-june-1-2026",
  "meeting_id": "01HQX5...",
  "title": "City Council meeting briefing for June 1, 2026",
  "meeting_date": "June 1, 2026",
  "status": "briefing_ready",
  "reading_time_minutes": 8,
  "generated_at": "2026-05-13T14:22:08Z",

  "meeting": {
    "id": "01HQX5...",
    "name": "City Council",
    "body": "City Council",
    "type": "city_council",
    "scheduled_at": "2026-06-01T18:00:00-05:00",
    "location": "City Hall Council Chambers"
  },

  "executive_summary": "The following items on your agenda require action and/or have a vote:",

  "agenda": [
    {
      "id": "01HQX7K9P1AE3Z3GZB1T5V8M9R-01",
      "title": "Call to order",
      "kind": "procedural",
      "has_briefing": false
    },
    {
      "id": "01HQX7K9P1AE3Z3GZB1T5V8M9R-06",
      "title": "Public Safety Camera Expansion",
      "kind": "action",
      "has_briefing": true
    }
  ],

  "action_items": [
    {
      "id": "01HQX7K9P1AE3Z3GZB1T5V8M9R-06",
      "title": "Public Safety Camera Expansion",
      "overview": "You're voting on the vendor contract and camera locations across the city...",
      "constituent_sentiment": {
        "summary": "72% support, 18% oppose",
        "detail": "Northside support climbs to 81%. Camera-request volume from the Ramsey corridor is 3.4x the citywide average over the last 12 months.",
        "sources": ["haystack"]
      },
      "recent_news": [
        {
          "title": "Council weighs camera expansion as Northside residents press for action",
          "outlet": "Burnsville Sentinel",
          "url": "https://www.burnsvillesentinel.com/cameras"
        }
      ],
      "budget_impact": {
        "summary": "$1.2M one-time install plus $180K per year ops. Spread across the levy, that's about $8.40 per household one-time and $1.30 per household per year ongoing.",
        "sources": [{
          "id": "src-2",
          "label": "burnsvillemn.gov",
          "kind": "official",
          "icon_initial": "B",
          "url": "https://burnsvillemn.gov"
        }]
      },
      "talking_points": [
        "72% citywide support and 81% on the Northside. The location map should reflect where the demand actually is.",
        "Councilmember Brennan voted yes on the 2024 downtown camera package on a 65% support read; this proposal has higher support and 3.4x the request volume in the underserved blocks.",
        "Ask Councilmember Pak to attach the same quarterly privacy and access audit clause she pushed for on the 2024 body-cam contract."
      ],
      "sources": [
        {
          "id": "haystack",
          "label": "Good Party internal data",
          "kind": "internal",
          "icon_initial": "G",
          "url": null
        },
        {
          "id": "src-2",
          "label": "burnsvillemn.gov",
          "kind": "official",
          "icon_initial": "B",
          "url": "https://burnsvillemn.gov"
        }
      ]
    }
  ]
}
