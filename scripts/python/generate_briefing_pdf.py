"""
Generate a PDF briefing document from a markdown file.
Usage: uv run generate_briefing_pdf.py INPUT.md OUTPUT.pdf
"""

import sys
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable

# ── Colors ────────────────────────────────────────────────────────────────────
NAVY       = HexColor("#1B3A6B")
BLUE       = HexColor("#2E6DA4")
LIGHT_BLUE = HexColor("#EBF2FA")
AMBER      = HexColor("#D97706")
GREEN      = HexColor("#15803D")
GRAY       = HexColor("#6B7280")
LIGHT_GRAY = HexColor("#F3F4F6")
POLL_BG    = HexColor("#FFF7ED")
POLL_BORDER= HexColor("#F59E0B")

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    styles = {}

    styles["title"] = ParagraphStyle("title",
        fontSize=24, fontName="Helvetica-Bold", textColor=NAVY,
        leading=30, spaceAfter=6)

    styles["subtitle"] = ParagraphStyle("subtitle",
        fontSize=13, fontName="Helvetica", textColor=GRAY,
        leading=18, spaceAfter=20)

    styles["h1"] = ParagraphStyle("h1",
        fontSize=14, fontName="Helvetica-Bold", textColor=white,
        leading=20, spaceBefore=14, spaceAfter=0,
        leftIndent=8, rightIndent=8)

    styles["h2"] = ParagraphStyle("h2",
        fontSize=12, fontName="Helvetica-Bold", textColor=NAVY,
        leading=16, spaceBefore=12, spaceAfter=4)

    styles["h3"] = ParagraphStyle("h3",
        fontSize=10, fontName="Helvetica-Bold", textColor=BLUE,
        leading=14, spaceBefore=8, spaceAfter=2)

    styles["body"] = ParagraphStyle("body",
        fontSize=9.5, fontName="Helvetica", textColor=black,
        leading=14, spaceAfter=6)

    styles["bullet"] = ParagraphStyle("bullet",
        fontSize=9.5, fontName="Helvetica", textColor=black,
        leading=14, spaceAfter=3,
        leftIndent=16, bulletIndent=6)

    styles["bold_bullet"] = ParagraphStyle("bold_bullet",
        fontSize=9.5, fontName="Helvetica-Bold", textColor=black,
        leading=14, spaceAfter=3,
        leftIndent=16, bulletIndent=6)

    styles["poll_title"] = ParagraphStyle("poll_title",
        fontSize=10, fontName="Helvetica-Bold", textColor=AMBER,
        leading=14, spaceAfter=4)

    styles["poll_body"] = ParagraphStyle("poll_body",
        fontSize=9, fontName="Helvetica", textColor=black,
        leading=13, spaceAfter=3)

    styles["poll_label"] = ParagraphStyle("poll_label",
        fontSize=9, fontName="Helvetica-Bold", textColor=black,
        leading=13, spaceAfter=1)

    styles["th_white"] = ParagraphStyle("th_white",
        fontSize=8.5, fontName="Helvetica-Bold", textColor=white,
        leading=12)

    styles["td"] = ParagraphStyle("td",
        fontSize=9, fontName="Helvetica", textColor=black, leading=12)

    styles["td_bold"] = ParagraphStyle("td_bold",
        fontSize=9, fontName="Helvetica-Bold", textColor=black, leading=12)

    styles["citation"] = ParagraphStyle("citation",
        fontSize=8, fontName="Helvetica-Oblique", textColor=GRAY,
        leading=11, spaceAfter=4)

    styles["appendix_item"] = ParagraphStyle("appendix_item",
        fontSize=9, fontName="Helvetica", textColor=black,
        leading=14, spaceAfter=2)

    return styles


# ── Section header helper ─────────────────────────────────────────────────────
def section_header(title, styles, usable_width):
    p = Paragraph(title, styles["h1"])
    tbl = Table([[p]], colWidths=[usable_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), NAVY),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    return tbl


# ── Poll callout helper ───────────────────────────────────────────────────────
def poll_callout(lines, styles, usable_width):
    """lines: list of (label, text) or (None, text) tuples"""
    inner = []
    inner.append(Paragraph("📊  GOOD PARTY POLLING OPPORTUNITY", styles["poll_title"]))
    for label, text in lines:
        if label:
            inner.append(Paragraph(f"<b>{label}</b> {text}", styles["poll_body"]))
        else:
            inner.append(Paragraph(text, styles["poll_body"]))

    tbl = Table([[inner]], colWidths=[usable_width - 24])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), POLL_BG),
        ("LINEAFTER",     (0,0), (0,-1),  4, POLL_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
    ]))
    return tbl


# ── Page numbering ────────────────────────────────────────────────────────────
def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawRightString(
        doc.pagesize[0] - 0.75*inch,
        0.5*inch,
        f"Page {canvas.getPageNumber()}"
    )
    canvas.setFillColor(NAVY)
    canvas.drawString(0.75*inch, 0.5*inch, "Village of Minooka | Trustee Briefing | March 2026")
    canvas.restoreState()


# ── Tier color ────────────────────────────────────────────────────────────────
def tier_color(score):
    try:
        s = float(score)
        if s >= 75: return HexColor("#DCFCE7"), GREEN
        if s >= 60: return LIGHT_BLUE, BLUE
        if s >= 50: return HexColor("#FEF9C3"), AMBER
        return LIGHT_GRAY, GRAY
    except Exception:
        return white, black


# ── Main ──────────────────────────────────────────────────────────────────────
def build_pdf(input_md, output_pdf):
    styles = make_styles()

    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=letter,
        leftMargin=0.75*inch, rightMargin=0.75*inch,
        topMargin=0.75*inch, bottomMargin=0.85*inch,
    )
    usable_width = letter[0] - 1.5*inch
    story = []

    # ── Title page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Briefing for Trustee Josh Stell", styles["title"]))
    story.append(Paragraph("Village of Minooka &nbsp;·&nbsp; March 2026", styles["subtitle"]))
    story.append(HRFlowable(width=usable_width, thickness=2, color=NAVY, spaceAfter=20))

    intro = ("This briefing provides a transition roadmap for your first 90 days as Village Trustee. "
             "It covers constituent priorities drawn from Haystaq voter data, key lessons from recent "
             "village history, early win opportunities, and context on the major policy debates you're "
             "stepping into. Use it to hit the ground running.")
    story.append(Paragraph(intro, styles["body"]))
    story.append(Spacer(1, 0.2*inch))

    # ── Section 1: Executive Summary ──────────────────────────────────────────
    story.append(section_header("1.  Executive Summary", styles, usable_width))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "You're stepping into a Village Board navigating one of the most consequential growth moments "
        "in Minooka's history. Two landmark projects — a $2B+ Equinix data center and the Canadian "
        "National intermodal facility — will define the village's economic and quality-of-life trajectory "
        "for the next decade. Constituent data shows public safety (58.3) and economic policy (56.8) as "
        "top resident priorities, consistent with a community that wants responsible growth without "
        "sacrificing the safe, small-town character that drew families here. The board's tone has been "
        "pragmatic and largely unified, but the CN railroad fight and data center scrutiny have raised "
        "the stakes for how the village manages outside pressure.",
        styles["body"]))

    story.append(Paragraph("<b>Your First 90 Days: Top 4 Focus Areas</b>", styles["h2"]))
    focus_areas = [
        ("<b>1. CN railroad lawsuit and enforcement readiness.</b>",
         " The CN facility opens in 2026. Your stated position on truck routes aligns with the village's, "
         "and you can be an effective public advocate. Get fully briefed before the facility opens."),
        ("<b>2. Equinix data center — community benefit conditions.</b>",
         " Construction begins in 2026. Residents raised real concerns about water, energy, and noise. "
         "Push for formal fiber-access commitments before construction contracts are finalized."),
        ("<b>3. Fiber-optic rollout completion.</b>",
         " Service is expected by end of 2026. Use your technology background to keep this on track and "
         "pair it with a small business development strategy."),
        ("<b>4. Fiscal accountability and transparency.</b>",
         " Establish yourself as the board's transparency voice — propose your conflict-of-interest "
         "disclosure ordinance early and engage actively in the FY2026–2027 budget process."),
    ]
    for bold, rest in focus_areas:
        story.append(Paragraph(f"• {bold}{rest}", styles["bullet"]))
    story.append(Spacer(1, 8))

    # ── Section 2: Lessons Learned ────────────────────────────────────────────
    story.append(section_header("2.  Lessons Learned From Recent History", styles, usable_width))
    story.append(Spacer(1, 6))

    lessons = [
        ("The CN fight shows Minooka can punch above its weight — if it acts early.",
         "The village filed a federal lawsuit before the facility opened. Early action bought leverage. "
         "When the CN facility opens in 2026, enforcement and monitoring need to be ready."),
        ("Big development requires active community management, not just zoning approval.",
         "The Equinix September 2025 open house drew 100+ residents with pointed questions — after zoning "
         "was already approved in December 2024. Future approvals should pair votes with proactive communication."),
        ("A 12% tax levy increase is defensible if you explain it clearly.",
         "The 2025 levy increase funded two new officers and triggered the village's first truth-in-taxation "
         "hearing. Transparent framing turned a potential controversy into a non-event — most homeowners saw "
         "their tax bill drop due to rising commercial valuations."),
        ("Younger residents are disengaged by default, not by choice.",
         "~70% of Minooka residents are under 55, yet no board member was below that age before your election. "
         "Your 587-vote win signals an appetite for different representation. Exercise that mandate consistently, "
         "especially on growth decisions affecting people who plan to live here for 30 more years."),
        ("Regional collaboration is more effective than going it alone.",
         "The intergovernmental Regional Infrastructure Collaboration Plan with Grundy County and four neighboring "
         "villages is a direct response to the CN challenge. Minooka's leverage is significantly stronger when "
         "neighboring municipalities are aligned. Protect and deepen those relationships."),
    ]
    for i, (title, body) in enumerate(lessons, 1):
        story.append(Paragraph(f"<b>{i}. {title}</b>", styles["h3"]))
        story.append(Paragraph(body, styles["body"]))

    # ── Section 3: Quick Wins ─────────────────────────────────────────────────
    story.append(section_header("3.  Quick Wins", styles, usable_width))
    story.append(Spacer(1, 6))

    qw = [
        ("Host a public CN railroad update before the facility opens.",
         "Organize a public update laying out where the litigation stands, the village's enforcement plan, "
         "and how residents can report truck violations. Directly addresses the public safety concern that "
         "is top-of-mind and builds trust before the problem arrives."),
        ("Create a fiber-optic progress tracker.",
         "Put a simple public dashboard or monthly board update in place showing rollout progress by area. "
         "Demonstrates responsive governance on your signature campaign issue and keeps the vendor accountable."),
        ("Introduce a conflict-of-interest disclosure ordinance.",
         "You made this a campaign promise. Proposing it in your first 90 days is achievable, costs nothing, "
         "and sets a transparency tone for your tenure immediately."),
        ("Meet with Village Administrator Duffy and department heads in your first 30 days.",
         "Your effectiveness depends on working relationships with staff. Understanding the budget, active "
         "projects, and pending decisions before they hit the board will make you a stronger voice for residents."),
        ("Champion fiber access in Equinix negotiations before construction starts.",
         "Equinix indicated openness to leveraging their fiber infrastructure for community broadband. Push "
         "for a formal board-level discussion before construction contracts are finalized — once building "
         "starts, attaching community benefit conditions becomes much harder."),
    ]
    for i, (title, body) in enumerate(qw, 1):
        story.append(Paragraph(f"<b>{i}. {title}</b>", styles["h3"]))
        story.append(Paragraph(body, styles["body"]))

    story.append(Spacer(1, 6))
    story.append(poll_callout([
        ("Issue:", "CN Railroad Truck Route Enforcement Priorities"),
        ("Timing:", "Poll before the CN facility opens (mid-2026)"),
        (None, "<b>Key Questions:</b>"),
        (None, "• How concerned are you about increased truck traffic on Ridge Road once the CN facility opens?"),
        (None, "• Which enforcement approach do you prefer: weight limit enforcement, alternate routes, or both?"),
        (None, "• How should the village prioritize this relative to other infrastructure spending?"),
        ("Why This Matters:", "Public safety scores are the highest in constituent data (58.3), but polling clarifies "
         "whether residents want aggressive enforcement action or are comfortable with the current legal strategy. "
         "Gives you a mandate before the facility opens."),
        ("Action:", "Contact Good Party to set up a community poll before summer 2026."),
    ], styles, usable_width))
    story.append(Spacer(1, 8))

    # ── Section 4: Constituents' Top Issues ──────────────────────────────────
    story.append(section_header("4.  Your Constituents' Top Issues", styles, usable_width))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Based on Haystaq voter data for 10,638 registered voters in Minooka, IL. "
        "Scores reflect average constituent sentiment (0–100 scale).",
        styles["body"]))

    story.append(Paragraph("<b>Demographics at a Glance</b>", styles["h2"]))
    demo_data = [
        [Paragraph("Metric", styles["th_white"]), Paragraph("Value", styles["th_white"])],
        [Paragraph("Total Registered Voters", styles["td"]), Paragraph("10,638", styles["td_bold"])],
        [Paragraph("Average Age", styles["td"]),             Paragraph("48.1 years", styles["td"])],
        [Paragraph("Gender Split", styles["td"]),            Paragraph("48% Male / 52% Female", styles["td"])],
    ]
    demo_tbl = Table(demo_data, colWidths=[usable_width*0.5, usable_width*0.5])
    demo_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("BACKGROUND",    (0,2), (-1,2),  LIGHT_GRAY),
        ("GRID",          (0,0), (-1,-1), 0.5, HexColor("#D1D5DB")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]))
    story.append(demo_tbl)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Top Issues by Priority</b> (Local/State Authority Only)", styles["h2"]))
    issue_rows = [
        ("1", "Public Safety",          "58.3", "Moderate (50–59)"),
        ("2", "Police Trust",            "58.7", "Moderate (50–59)"),
        ("3", "Conservative Ideology",  "59.5", "Moderate (50–59)"),
        ("4", "Economic Policy",        "56.8", "Moderate (50–59)"),
        ("5", "Environment",            "47.0", "Below Threshold"),
        ("6", "Education Funding",      "44.0", "Below Threshold"),
        ("7", "Infrastructure",         "43.4", "Below Threshold"),
        ("8", "Housing (Gov Role)",     "38.8", "Below Threshold"),
        ("9", "Public Transit",         "40.4", "Below Threshold"),
        ("10","Helping People",         "38.7", "Below Threshold"),
    ]
    issue_header = [
        Paragraph("Rank",  styles["th_white"]),
        Paragraph("Issue", styles["th_white"]),
        Paragraph("Score", styles["th_white"]),
        Paragraph("Tier",  styles["th_white"]),
    ]
    issue_data = [issue_header]
    for rank, issue, score, tier in issue_rows:
        bg, fg = tier_color(score)
        issue_data.append([
            Paragraph(rank,  styles["td"]),
            Paragraph(issue, styles["td"]),
            Paragraph(score, styles["td_bold"]),
            Paragraph(tier,  styles["td"]),
        ])

    issue_tbl = Table(issue_data,
        colWidths=[usable_width*0.08, usable_width*0.40,
                   usable_width*0.14, usable_width*0.38])
    style_cmds = [
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("GRID",          (0,0), (-1,-1), 0.5, HexColor("#D1D5DB")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
    ]
    for i, (_, _, score, _) in enumerate(issue_rows, 1):
        bg, _ = tier_color(score)
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    issue_tbl.setStyle(TableStyle(style_cmds))
    story.append(issue_tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>Note: No issues scored in Tier 1 (75+) or Tier 2 (60–74). Minooka is a moderate-conservative "
        "community. Public safety and economic policy are clear relative priorities.</i>",
        styles["citation"]))

    story.append(Spacer(1, 6))
    story.append(poll_callout([
        ("Issue:", "Growth vs. Community Character Tradeoffs"),
        ("Timing:", "Before major Equinix construction approvals (spring 2026)"),
        (None, "<b>Key Questions:</b>"),
        (None, "• How important is it that new development maintains Minooka's small-town character?"),
        (None, "• Would you prioritize tax revenue from the data center over concerns about water and energy costs?"),
        (None, "• What types of businesses would you most like to see come to Minooka in the next 5 years?"),
        ("Why This Matters:", "Haystaq doesn't capture the specific development tradeoffs Minooka is navigating. "
         "Polling gives you real constituent data before the board makes irreversible decisions."),
        ("Action:", "Contact Good Party for a community development priorities poll before April 2026."),
    ], styles, usable_width))
    story.append(Spacer(1, 8))

    # ── Section 5: What to Watch ──────────────────────────────────────────────
    story.append(section_header("5.  What to Watch & Prepare For", styles, usable_width))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Issues Requiring Immediate Attention</b>", styles["h2"]))
    watch = [
        ("<b>CN facility opening (2026).</b>",
         " The intermodal facility opens this year and the federal lawsuit is still pending. The board "
         "needs a clear enforcement plan before trucks start moving."),
        ("<b>Equinix construction launch.</b>",
         " Construction begins in 2026. Community concerns from the September 2025 open house (water, noise, "
         "energy) haven't been fully resolved. A proactive communication plan is needed."),
        ("<b>FY 2026–2027 budget cycle (starts May 1).</b>",
         " The 2025 levy increase funded two new officers; the board will need to decide on continued "
         "expansion vs. redirecting resources. Watch for pension and infrastructure maintenance pressures."),
    ]
    for bold, rest in watch:
        story.append(Paragraph(f"• {bold}{rest}", styles["bullet"]))

    story.append(Paragraph("<b>Political Dynamics to Understand</b>", styles["h2"]))
    dynamics = [
        ("<b>Village President Ric Offerman</b>",
         " has been the public face of the CN fight and is philosophically aligned with responsible growth. "
         "You start with a productive relationship, but watch for fiscal vs. growth tensions."),
        ("<b>Village Administrator Dan Duffy</b>",
         " is the operational backbone. Your effectiveness as a trustee depends on a strong working "
         "relationship with him — he's your best resource for understanding day-to-day reality."),
        ("<b>You are the only independent and youngest trustee by a significant margin.</b>",
         " Build relationships with other trustees proactively rather than waiting for votes to align you."),
    ]
    for bold, rest in dynamics:
        story.append(Paragraph(f"• {bold}{rest}", styles["bullet"]))

    story.append(Paragraph("<b>Upcoming Challenges or Decisions</b>", styles["h2"]))
    upcoming = [
        ("<b>CN lawsuit resolution.</b>",
         " A federal court decision could come at any time. Understand the full legal posture before that happens."),
        ("<b>Equinix formal approvals.</b>",
         " As construction moves from planning to execution, additional permits will be required — each one "
         "is an opportunity to attach community benefit conditions."),
        ("<b>Police staffing and pension costs.</b>",
         " Two new officers were funded in 2025. Pension obligations are a growing line item. "
         "The board will face recurring decisions about sustainable public safety funding as the village grows."),
    ]
    for bold, rest in upcoming:
        story.append(Paragraph(f"• {bold}{rest}", styles["bullet"]))
    story.append(Spacer(1, 8))

    # ── Section 6: Understanding This Role ───────────────────────────────────
    story.append(section_header("6.  Understanding This Role", styles, usable_width))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>What Is Expected</b>", styles["h2"]))
    story.append(Paragraph(
        "The Village of Minooka operates with a Village President (elected separately) and six Trustees, "
        "supported by Village Administrator Dan Duffy who manages day-to-day operations. As a Trustee, "
        "your job is to vote on ordinances, resolutions, and budgets — not to manage departments or direct "
        "staff. You represent the entire village, not a specific district. Board meetings are held the "
        "fourth Tuesday of each month at 6:30 PM at Village Hall. Committee work (Economic Development, "
        "Ordinance & Building, Public Safety) is where trustees build real policy influence — engage there early.",
        styles["body"]))

    story.append(Paragraph("<b>What Is Outside the Scope</b>", styles["h2"]))
    story.append(Paragraph(
        "You are not an ombudsman, a project manager, or a department supervisor. When residents bring "
        "individual complaints — a pothole, a permit problem, a neighbor dispute — direct them to the right "
        "staff person. Intervening in day-to-day operations undermines the administrator and burns your "
        "political capital on things staff handles better. Federal issues (immigration, federal infrastructure "
        "funding, national law) are largely outside village authority, though they may affect Minooka — the "
        "CN railroad's federal preemption argument is a direct example of this tension.",
        styles["body"]))

    story.append(Paragraph("<b>How to Represent Your Community</b>", styles["h2"]))
    story.append(Paragraph(
        "The Haystaq data is your best tool for avoiding the vocal minority trap. At 10,638 registered "
        "voters, the people who attend board meetings are a tiny, self-selected slice of Minooka. Public "
        "safety and economic policy are genuine community priorities — but the data shows they're moderate "
        "concerns (50s range), not crisis-level demands. Use this to calibrate responses: listen to everyone, "
        "but weight your decisions toward what the broader community cares about. Your transparency mandate "
        "is best exercised through consistent, proactive communication — explaining decisions before they're "
        "made, disclosing your own reasoning publicly, and using polling to demonstrate you're representing "
        "constituents, not just your own instincts.",
        styles["body"]))
    story.append(Spacer(1, 8))

    # ── Section 7: Budget Discussions ────────────────────────────────────────
    story.append(section_header("7.  Top 3 Budget Discussions (Past 12 Months)", styles, usable_width))
    story.append(Spacer(1, 6))

    budget_items = [
        (
            "1.  2025 Tax Levy Approval — 12% Increase for Police Expansion",
            "December 2025",
            [
                "Board approved ~12% increase to the property tax levy: $440,000 of a $3.5M total levy",
                "Primary use: hiring two new police officers; secondary: new snowplow, pension obligations",
                "Village held its first truth-in-taxation hearing; ~20 residents attended",
                "Most homeowners will see tax bills drop by $12–14 due to rising commercial/industrial valuations",
            ],
            "Levy approved.",
            "The police expansion and pension obligations recur in the next budget. Understand the full "
            "personnel cost trajectory — not just salaries but long-term pension liabilities — before "
            "voting on the FY2026–2027 levy.",
            "https://www.wcsjnews.com/news/local/minooka-trustees-approve-2025-tax-levy/article_616eb960-e0b8-4336-b23a-97e7472c3acd.html",
            "WCSJ News, 2025 Tax Levy"
        ),
        (
            "2.  FY 2025–2026 Operating Budget — ~$11 Million",
            "Spring 2025",
            [
                "Total operating budget ~$11M; roughly one-third ($3.5M) funded through property tax levy",
                "Budget covers public safety, public works, administration, and capital projects",
                "Fiscal year runs May 1 – April 30; FY2026–2027 budget process begins spring 2026",
                "Village has secured $800,000 in combined private and state funding for park improvements",
            ],
            "Budget adopted.",
            "With Equinix projected to generate $3M in its first five years and up to $7M over 10 years, "
            "the next budget cycle involves decisions about how to allocate incoming revenue — infrastructure, "
            "reserves, or tax relief. This is a defining fiscal decision aligned with your platform.",
            "https://www.minooka.com/our-government/finance-department/budget-and-finances/",
            "Village of Minooka Budget & Finances"
        ),
        (
            "3.  Park Improvements — $800,000 in Combined Funding",
            "2025",
            [
                "$800,000 secured in combined private and state funding for park amenity improvements",
                "Demonstrates the village's capacity to leverage outside funding rather than additional taxes",
                "Investments include enhanced recreational facilities supporting quality of life",
            ],
            "Projects approved and underway.",
            "As you think about fiber-optic access, EV charging, and other infrastructure investments, "
            "the model of pairing village advocacy with state grants and private partnerships is worth replicating.",
            "https://www.shawlocal.com/morris-herald-news/2026/01/04/community-pulse-whats-happening-in-minooka/",
            "Shaw Local, Community Pulse, January 2026"
        ),
    ]

    for title, date, bullets, outcome, matters, url, url_label in budget_items:
        story.append(Paragraph(f"<b>{title}</b>", styles["h3"]))
        story.append(Paragraph(f"<i>{date}</i>", styles["citation"]))
        for b in bullets:
            story.append(Paragraph(f"• {b}", styles["bullet"]))
        story.append(Paragraph(f"<b>Outcome:</b> {outcome} "
                               f'<a href="{url}"><font color="#2E6DA4"><i>[{url_label}]</i></font></a>',
                               styles["body"]))
        story.append(Paragraph(f"<b>Why This Matters for You:</b> {matters}", styles["body"]))
        story.append(Spacer(1, 6))

    # ── Section 8: Policy Discussions ────────────────────────────────────────
    story.append(section_header("8.  Top 3 Non-Budget Policy Discussions (Past 18 Months)", styles, usable_width))
    story.append(Spacer(1, 6))

    policy_items = [
        (
            "1.  CN Railroad Intermodal Facility — Truck Traffic Lawsuit",
            "June 2024 – Present",
            [
                "CN Railway planned a 900-acre intermodal facility in Channahon, routing ~900,000 diesel trucks/year through Minooka's commercial district to access I-80",
                "Village filed federal lawsuit June 2024 seeking weight limits on McLindon Road; CN declined to alter routing, citing federal preemption",
                "~25% of CN trucks would route through Ridge Road — where half of village accidents already occur",
                "Four daily 2-mile trains could block intersections for up to 20 minutes each",
                "Village joined Regional Infrastructure Collaboration Plan with Grundy County and four neighboring municipalities",
            ],
            "Lawsuit pending in U.S. District Court for Northern Illinois; facility set to open 2026.",
            "This is the most active policy fight you're walking into. The facility opens this year. "
            "You need to understand the litigation posture, the enforcement plan, and the regional coalition "
            "strategy before your first board vote touches this issue.",
            "https://www.chicagotribune.com/2024/06/22/minooka-pushes-back-on-massive-rail-project-it-says-will-flood-village-with-truck-traffic/",
            "Chicago Tribune, June 2024"
        ),
        (
            "2.  Equinix Data Center — Zoning and Community Process",
            "January 2025 – Present",
            [
                "Equinix proposed a $2B+ data center campus on ~300 acres at Holt and Ridge Road; initial presentation January 23, 2025",
                "Board approved 'Data Center District' zoning in December 2024",
                "September 2025 open house drew 100+ residents with concerns about water usage, energy costs, and noise",
                "Equinix confirmed air-cooled design; sound shrouds and natural plantings for noise mitigation",
                "Projected revenue: up to $7M in taxes over 10 years; potentially $20M annually at full build-out; 160+ permanent jobs",
            ],
            "Zoning approved; construction expected to begin 2026.",
            "You raised the idea of leveraging Equinix's fiber infrastructure for resident broadband. "
            "Equinix indicated openness. Push for a formal board-level commitment before construction "
            "contracts are finalized — once construction starts, conditions become much harder to attach.",
            "https://patch.com/illinois/channahon-minooka/equinix-proposes-billion-dollar-data-center-investment-minooka-nodx",
            "Patch, Channahon-Minooka, January 2025"
        ),
        (
            "3.  Fiber-Optic Internet Expansion",
            "2025 – Present",
            [
                "Village actively deploying fiber-optic infrastructure; service expected for residents and businesses by end of 2026",
                "Additional technology investments: EV charging stations planned for downtown and Village Hall, online permitting recently launched",
                "Motive Power Resources received state funding to manufacture electric locomotives in Minooka",
                "New residential and commercial development underway: 54-home Lennar development, senior duplexes, hotel under construction",
            ],
            "Rollout underway; completion expected end of 2026.",
            "This is your signature campaign issue and it's already in motion. Your job is to ensure "
            "it completes on schedule, reaches all parts of the village equitably, and is paired with "
            "a business development strategy that turns connectivity into economic activity.",
            "https://www.shawlocal.com/morris-herald-news/2026/01/04/community-pulse-whats-happening-in-minooka/",
            "Shaw Local, Community Pulse, January 2026"
        ),
    ]

    for title, date, bullets, outcome, matters, url, url_label in policy_items:
        story.append(Paragraph(f"<b>{title}</b>", styles["h3"]))
        story.append(Paragraph(f"<i>{date}</i>", styles["citation"]))
        for b in bullets:
            story.append(Paragraph(f"• {b}", styles["bullet"]))
        story.append(Paragraph(f"<b>Outcome:</b> {outcome} "
                               f'<a href="{url}"><font color="#2E6DA4"><i>[{url_label}]</i></font></a>',
                               styles["body"]))
        story.append(Paragraph(f"<b>Why This Matters for You:</b> {matters}", styles["body"]))
        story.append(Spacer(1, 6))

    # ── Appendix ──────────────────────────────────────────────────────────────
    story.append(section_header("Appendix:  Key Resources", styles, usable_width))
    story.append(Spacer(1, 6))

    appendix = [
        ("Board Meetings",       "Fourth Tuesday of each month, 6:30 PM — Village Hall, 121 E. McEvilly Road, Minooka, IL 60447"),
        ("Village President",    "Ric Offerman"),
        ("Village Administrator","Dan Duffy — (815) 467-2151 | info@minooka.com"),
        ("Fellow Trustees",      "Dennis Martin, Gabriela Martinez, Ray Mason, Barry Thompson, Robin White"),
        ("Agendas & Minutes",    "minooka.com/our-government/agendas-minutes"),
        ("Budget & Finances",    "minooka.com/our-government/finance-department/budget-and-finances"),
        ("All Village Events",   "events.minooka.com/village"),
        ("Total Budget",         "~$11 million operating | $3.5M property tax levy (12% increase, December 2025)"),
        ("Equinix Revenue",      "~$3M in first 5 years | up to $7M over 10 years (projected)"),
    ]
    for label, value in appendix:
        story.append(Paragraph(f"<b>{label}:</b>  {value}", styles["appendix_item"]))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF generated: {output_pdf}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run generate_briefing_pdf.py INPUT.md OUTPUT.pdf")
        sys.exit(1)
    build_pdf(sys.argv[1], sys.argv[2])
