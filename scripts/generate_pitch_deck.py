#!/usr/bin/env python3
"""Generate the Fiducia 3-minute pitch deck.

The deck intentionally uses only native PowerPoint shapes and text so it can be
edited quickly before the live presentation and does not depend on external
image assets.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Fiducia_Pitch_Deck.pptx"

SLIDE_W = 13.333
SLIDE_H = 7.5

# Exact UI tokens from app.py, with two presentation-specific neutrals.
INK = "071321"
PANEL = "0D2033"
PANEL_2 = "0A1A2A"
PANEL_3 = "102D41"
LINE = "254157"
LINE_SOFT = "1B3448"
TEAL = "19C6B3"
GOLD = "F4B942"
MUTED = "91A7B8"
WHITE = "F3F7FA"
SOFT_WHITE = "D3DCE4"
GREEN = "57D49B"
RED = "FF6B6B"
BLUE = "58A6D6"
DEEP_TEAL = "0D282E"
DEEP_GOLD = "2B2515"
DEEP_RED = "2A171D"

TITLE_FONT = "Manrope"
BODY_FONT = "DM Sans"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def add_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str = PANEL,
    line: str | None = LINE,
    radius: bool = True,
    line_width: float = 1.0,
):
    kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
    shape = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(line_width)
    return shape


def add_line(
    slide,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    color: str = LINE,
    width: float = 1.5,
):
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    line.line.color.rgb = rgb(color)
    line.line.width = Pt(width)
    return line


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    color: str = WHITE,
    bold: bool = False,
    font: str = BODY_FONT,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    margin: float = 0.0,
    line_spacing: float = 1.0,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    p.space_after = Pt(0)
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return box


def add_rich_line(
    slide,
    runs: list[tuple[str, str, float, bool, str]],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(0)
    for text_value, color, size, bold, font in runs:
        run = p.add_run()
        run.text = text_value
        run.font.name = font
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
    return box


def add_pill(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    *,
    fill: str = PANEL_2,
    line: str = LINE,
    color: str = MUTED,
    size: float = 9,
    bold: bool = True,
):
    add_rect(slide, x, y, w, 0.34, fill=fill, line=line, radius=True)
    add_text(
        slide,
        text,
        x + 0.08,
        y + 0.005,
        w - 0.16,
        0.32,
        size=size,
        color=color,
        bold=bold,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )


def add_badge(
    slide,
    text: str,
    x: float,
    y: float,
    *,
    fill: str,
    color: str = INK,
    diameter: float = 0.34,
    size: float = 10,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.OVAL,
        Inches(x),
        Inches(y),
        Inches(diameter),
        Inches(diameter),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.fill.background()
    add_text(
        slide,
        text,
        x,
        y,
        diameter,
        diameter,
        size=size,
        color=color,
        bold=True,
        align=PP_ALIGN.CENTER,
        valign=MSO_ANCHOR.MIDDLE,
    )


def add_bullets(
    slide,
    items: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 13,
    color: str = SOFT_WHITE,
    bullet_color: str = TEAL,
    gap: float = 0.43,
):
    for i, item in enumerate(items):
        yy = y + i * gap
        add_badge(slide, "", x, yy + 0.08, fill=bullet_color, diameter=0.09)
        add_text(slide, item, x + 0.19, yy, w - 0.19, min(0.42, h), size=size, color=color)


def add_chevron(slide, x: float, y: float, *, color: str = MUTED, size: float = 18):
    add_text(slide, "›", x, y, 0.22, 0.32, size=size, color=color, bold=True, align=PP_ALIGN.CENTER)


def add_base(slide, index: int, section: str, timing: str | None = None, *, backup: bool = False):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb(INK)

    # Quiet geometric halo, echoing the app's dark radial-gradient treatment.
    for x, y, d, line_color in [(10.7, -1.55, 4.2, "123A50"), (11.45, -0.82, 2.45, LINE_SOFT)]:
        ring = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
        ring.fill.background()
        ring.line.color.rgb = rgb(line_color)
        ring.line.width = Pt(1.1)

    # Brand mark.
    mark = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.54), Inches(0.34), Inches(0.35), Inches(0.35))
    mark.fill.solid()
    mark.fill.fore_color.rgb = rgb(TEAL)
    mark.line.fill.background()
    add_text(slide, "F", 0.54, 0.335, 0.35, 0.35, size=13, color=INK, bold=True, font=TITLE_FONT, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_text(slide, "FIDUCIA", 0.99, 0.37, 1.45, 0.24, size=11, color=WHITE, bold=True, font=TITLE_FONT)
    add_text(slide, section.upper(), 2.30, 0.39, 3.5, 0.20, size=8.5, color=TEAL, bold=True)

    if backup:
        add_pill(slide, "BACKUP", 10.76, 0.34, 0.86, fill=DEEP_GOLD, line="765F2E", color=GOLD, size=8)
    if timing:
        add_pill(slide, timing, 11.76, 0.34, 1.00, fill=PANEL_2, line=LINE, color=SOFT_WHITE, size=8)

    add_line(slide, 0.54, 7.17, 12.78, 7.17, color=LINE_SOFT, width=0.8)
    add_text(
        slide,
        "PROTOTYPE • SYNTHETIC DATA • ILLUSTRATIVE POLICY • NOT LEGAL OR INVESTMENT ADVICE",
        0.56,
        7.24,
        9.9,
        0.14,
        size=6.8,
        color="7890A2",
        bold=True,
    )
    add_text(slide, f"{index:02d}", 12.30, 7.21, 0.46, 0.17, size=8, color=MUTED, bold=True, align=PP_ALIGN.RIGHT)


def add_title(slide, title: str, subtitle: str, *, title_size: float = 31, y: float = 0.92, w: float = 12.0):
    add_text(slide, title, 0.58, y, w, 0.86, size=title_size, color=WHITE, bold=True, font=TITLE_FONT)
    add_text(slide, subtitle, 0.60, y + 0.81, w, 0.48, size=13, color=MUTED)


def slide_problem(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 1, "The problem", "0:00–0:45")

    add_text(
        slide,
        "Approval is a decision system—\nnot an inbox.",
        0.60,
        1.13,
        7.20,
        1.30,
        size=33,
        color=WHITE,
        bold=True,
        font=TITLE_FONT,
    )
    add_text(
        slide,
        "Analysts re-key facts. Specialists reconstruct context. Sponsors assemble the final story.",
        0.62,
        2.54,
        6.75,
        0.62,
        size=15,
        color=MUTED,
    )

    friction = [
        ("01", "FRAGMENTED", "Evidence lives across files, messages and versions."),
        ("02", "SERIAL", "Every handoff waits for the previous inbox."),
        ("03", "OPAQUE", "The ‘why’ is rebuilt after the decision."),
    ]
    for i, (num, label, copy) in enumerate(friction):
        x = 0.62 + i * 2.38
        add_rect(slide, x, 3.34, 2.16, 1.44, fill=PANEL_2, line=LINE)
        add_text(slide, num, x + 0.15, 3.51, 0.35, 0.22, size=8, color=TEAL, bold=True)
        add_text(slide, label, x + 0.15, 3.77, 1.78, 0.25, size=10, color=WHITE, bold=True, font=TITLE_FONT)
        add_text(slide, copy, x + 0.15, 4.10, 1.78, 0.52, size=10, color=MUTED)

    # Five role handoffs, shown as inbox fragments rather than a shared case.
    roles = [
        ("ANALYST", "normalize"),
        ("COMPLIANCE", "test rules"),
        ("GOVERNANCE", "plan fit"),
        ("FINANCE", "fee math"),
        ("SPONSOR", "synthesize"),
    ]
    x = 8.10
    y = 1.30
    for i, (role, task) in enumerate(roles):
        offset = 0.14 if i % 2 else 0
        xx = x + offset
        yy = y + i * 0.84
        add_rect(slide, xx, yy, 4.38, 0.64, fill=PANEL, line=LINE)
        add_badge(slide, str(i + 1), xx + 0.15, yy + 0.14, fill=LINE, color=SOFT_WHITE, diameter=0.34, size=9)
        add_text(slide, role, xx + 0.62, yy + 0.12, 1.50, 0.22, size=9.5, color=WHITE, bold=True, font=TITLE_FONT)
        add_text(slide, task, xx + 2.20, yy + 0.12, 1.08, 0.22, size=8.2, color=MUTED, align=PP_ALIGN.RIGHT)
        add_pill(slide, "INBOX", xx + 3.55, yy + 0.17, 0.64, fill=PANEL_2, line=LINE_SOFT, color=MUTED, size=6.5)
        if i < 4:
            add_text(slide, "↓", xx + 1.92, yy + 0.64, 0.25, 0.22, size=10, color="486579", bold=True, align=PP_ALIGN.CENTER)

    add_rect(slide, 0.62, 5.34, 11.90, 1.14, fill=PANEL_3, line="28516A")
    add_text(slide, "A fluent answer is not a control.", 0.91, 5.60, 5.30, 0.34, size=18, color=WHITE, bold=True, font=TITLE_FONT)
    add_text(slide, "Fiducia creates one case, one evidence chain and one accountable next action.", 6.35, 5.57, 5.72, 0.44, size=13, color=TEAL, bold=True, align=PP_ALIGN.RIGHT)


def slide_agents(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 2, "Five-agent solution", "0:45–1:05")
    add_title(
        slide,
        "Five bounded agents. One evidence chain.",
        "LangGraph owns state and routing. Deterministic code owns validation, math and decision gates.",
        title_size=30,
    )

    cards = [
        ("1", "ANALYST / REVIEWER", "Normalize intake", "schema • source lookup", TEAL),
        ("2", "COMPLIANCE", "Test policy", "controls • references", BLUE),
        ("3", "GOVERNANCE", "Evaluate plan fit", "risk band • lineup", GREEN),
        ("4", "FINANCE", "Compare true cost", "fees • breakpoints", GOLD),
        ("5", "DECISION OWNER", "Aggregate + route", "risk • recommendation", TEAL),
    ]
    card_w = 2.27
    xs = [0.58, 3.05, 5.52, 7.99, 10.46]
    for i in range(4):
        add_line(slide, xs[i] + card_w, 3.30, xs[i + 1], 3.30, color="486579", width=1.7)
        add_chevron(slide, xs[i] + card_w + 0.08, 3.14, color=MUTED)
    for x, (num, role, verb, tools, accent) in zip(xs, cards):
        add_rect(slide, x, 2.46, card_w, 1.82, fill=PANEL, line=accent, line_width=1.25)
        add_badge(slide, num, x + 0.17, 2.64, fill=accent, color=INK, diameter=0.38, size=10)
        add_text(slide, role, x + 0.66, 2.67, 1.43, 0.24, size=8.6, color=accent, bold=True, font=TITLE_FONT)
        add_text(slide, verb, x + 0.17, 3.19, 1.92, 0.31, size=14, color=WHITE, bold=True, font=TITLE_FONT)
        add_text(slide, tools, x + 0.17, 3.66, 1.92, 0.24, size=9, color=MUTED)

    # Three guardrail planes supporting the agent chain.
    lanes = [
        ("EVIDENCE PLANE", "source hash • typed nulls • as-of dates", TEAL),
        ("POLICY PLANE", "versioned rules • deterministic comparators", GOLD),
        ("AUDIT PLANE", "tool receipts • transitions • SHA-256 chain", GREEN),
    ]
    for i, (label, copy, accent) in enumerate(lanes):
        x = 0.60 + i * 4.08
        add_rect(slide, x, 4.72, 3.78, 0.78, fill=PANEL_2, line=LINE)
        add_text(slide, label, x + 0.16, 4.89, 1.26, 0.18, size=8, color=accent, bold=True)
        add_text(slide, copy, x + 1.38, 4.87, 2.17, 0.28, size=8.4, color=MUTED, align=PP_ALIGN.RIGHT)

    add_rect(slide, 0.60, 5.78, 8.70, 0.82, fill=PANEL_3, line="28516A")
    add_rich_line(
        slide,
        [
            ("The model may ", MUTED, 12, False, BODY_FONT),
            ("explain bounded findings", TEAL, 12, True, BODY_FONT),
            (". It may not invent a number, change a rule or approve its own exception.", SOFT_WHITE, 12, False, BODY_FONT),
        ],
        0.86,
        5.94,
        8.18,
        0.36,
    )
    add_line(slide, 10.73, 4.28, 10.73, 5.84, color=GOLD, width=1.2)
    add_chevron(slide, 10.62, 5.47, color=GOLD, size=16)
    add_rect(slide, 9.61, 5.78, 2.90, 0.82, fill=DEEP_GOLD, line="765F2E")
    add_text(slide, "GOVERNED HUMAN CHECKPOINT", 9.83, 5.95, 2.46, 0.20, size=8.7, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "approve • reject • return", 9.83, 6.22, 2.46, 0.18, size=8.5, color="F3D88A", align=PP_ALIGN.CENTER)


def slide_demo(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 3, "Live demo proof", "1:05–1:45")
    add_title(
        slide,
        "The demo proves behavior—not promises.",
        "Run DATA. Watch one bounded repair. Finish green.",
        title_size=30,
    )

    # Stylized cockpit frame.
    add_rect(slide, 0.58, 2.16, 8.52, 4.48, fill="091927", line=LINE, radius=True, line_width=1.2)
    add_text(slide, "FIDUCIA CONTROL PLANE", 0.86, 2.38, 2.45, 0.20, size=8.2, color=TEAL, bold=True)
    add_pill(slide, "DATA · SYNTHETIC", 6.93, 2.30, 1.73, fill=PANEL_2, line=LINE, color=SOFT_WHITE, size=7.5)

    node_names = ["ANALYST", "COMPLIANCE", "GOVERNANCE", "FINANCE", "SPONSOR"]
    node_xs = [0.86, 2.40, 3.94, 5.48, 7.02]
    for i, (name, x) in enumerate(zip(node_names, node_xs)):
        accent = GREEN
        add_rect(slide, x, 2.79, 1.32, 0.75, fill=DEEP_TEAL, line=accent)
        add_badge(slide, "✓", x + 0.10, 2.94, fill=accent, color=INK, diameter=0.27, size=7.5)
        add_text(slide, name, x + 0.44, 2.96, 0.77, 0.16, size=6.6, color=WHITE, bold=True)
        add_text(slide, "COMPLETE", x + 0.10, 3.25, 1.05, 0.14, size=5.8, color=accent, bold=True)
        if i < 4:
            add_chevron(slide, x + 1.33, 3.00, color="486579", size=13)

    add_rect(slide, 0.86, 3.83, 3.18, 2.32, fill=PANEL, line=LINE)
    add_text(slide, "SELF-CORRECTION", 1.05, 4.03, 1.45, 0.20, size=8.5, color=GOLD, bold=True)
    add_pill(slide, "RETRY 1 / 2", 2.75, 3.96, 1.02, fill=DEEP_GOLD, line="765F2E", color=GOLD, size=7)
    add_text(slide, "Sharpe ratio", 1.05, 4.51, 1.34, 0.22, size=10, color=MUTED)
    add_text(slide, "NULL", 3.02, 4.50, 0.62, 0.22, size=10, color=RED, bold=True, align=PP_ALIGN.RIGHT)
    add_line(slide, 1.05, 4.84, 3.75, 4.84, color=LINE_SOFT, width=0.8)
    add_text(slide, "Approved source", 1.05, 5.02, 1.34, 0.22, size=10, color=MUTED)
    add_text(slide, "FOUND", 2.93, 5.01, 0.71, 0.22, size=10, color=GREEN, bold=True, align=PP_ALIGN.RIGHT)
    add_rect(slide, 1.05, 5.45, 2.70, 0.43, fill=DEEP_TEAL, line="2D6E62")
    add_text(slide, "↻ validate again in the same case", 1.18, 5.55, 2.42, 0.18, size=8.3, color=GREEN, bold=True)

    add_rect(slide, 4.29, 3.83, 4.52, 2.32, fill=PANEL_3, line=GREEN, line_width=1.2)
    add_text(slide, "AGENT RECOMMENDATION", 4.54, 4.06, 2.07, 0.20, size=8.5, color=MUTED, bold=True)
    add_text(slide, "APPROVE", 4.54, 4.53, 3.36, 0.48, size=25, color=GREEN, bold=True, font=TITLE_FONT)
    add_text(slide, "Risk 0 / 100  •  Confidence 0.94", 4.54, 5.39, 3.47, 0.22, size=10, color=SOFT_WHITE)
    add_pill(slide, "COMPLETED · NO HUMAN TOUCH", 6.34, 5.48, 2.18, fill=DEEP_TEAL, line="2D6E62", color=GREEN, size=6.7)

    # Proof rail.
    proofs = [
        ("01", "GOLDEN PATH", "SUNX → APPROVE\nno human touch", GREEN),
        ("02", "RECOVERY", "DATA → retry 1/2\nsource recorded", TEAL),
        ("03", "CONTROL", "SPECX → REJECT\nhuman checkpoint", GOLD),
    ]
    for i, (num, label, copy, accent) in enumerate(proofs):
        y = 2.17 + i * 1.31
        add_rect(slide, 9.41, y, 3.10, 1.08, fill=PANEL_2, line=LINE)
        add_badge(slide, num, 9.61, y + 0.19, fill=accent, color=INK, diameter=0.36, size=7.5)
        add_text(slide, label, 10.10, y + 0.16, 2.05, 0.20, size=8.4, color=accent, bold=True)
        add_text(slide, copy, 10.10, y + 0.47, 2.02, 0.42, size=10.2, color=SOFT_WHITE)
    add_rect(slide, 9.41, 6.10, 3.10, 0.54, fill=PANEL_3, line="28516A")
    add_text(slide, "SHOW EVENTS, NOT HIDDEN CHAIN-OF-THOUGHT", 9.58, 6.27, 2.76, 0.16, size=7.2, color=TEAL, bold=True, align=PP_ALIGN.CENTER)


def slide_value_scale(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 4, "Governance + scale", "1:45–2:30")
    add_title(
        slide,
        "Scale the workflow—never the uncertainty.",
        "The prototype proves isolated case state and bounded retry; the production target adds queue-backed scale.",
        title_size=29,
    )

    # Scalable operating model on the left.
    add_rect(slide, 0.58, 2.18, 5.70, 3.86, fill=PANEL_2, line=LINE)
    add_text(slide, "PRODUCTION SCALE TARGET • NOT DEPLOYED", 0.86, 2.43, 3.42, 0.20, size=8.2, color=TEAL, bold=True)

    case_ys = [2.96, 3.54, 4.12]
    for i, yy in enumerate(case_ys, 1):
        add_rect(slide, 0.88, yy, 1.04, 0.39, fill=PANEL, line=LINE_SOFT)
        add_text(slide, f"CASE {i:02d}", 0.98, yy + 0.10, 0.83, 0.13, size=6.6, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
        add_line(slide, 1.93, yy + 0.20, 2.42, yy + 0.20, color="486579", width=1.0)
    add_rect(slide, 2.43, 3.16, 0.86, 1.18, fill=PANEL_3, line=TEAL)
    add_text(slide, "QUEUE", 2.54, 3.42, 0.64, 0.18, size=8, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "SQS", 2.54, 3.73, 0.64, 0.16, size=7.5, color=MUTED, align=PP_ALIGN.CENTER)
    add_line(slide, 3.29, 3.75, 3.73, 3.75, color="486579", width=1.2)

    worker_labels = ["ANALYST", "POLICY", "SUITABILITY", "COST"]
    for i, label in enumerate(worker_labels):
        yy = 2.76 + i * 0.66
        add_rect(slide, 3.74, yy, 1.55, 0.46, fill=PANEL, line=TEAL if i == 0 else LINE)
        add_text(slide, label, 3.89, yy + 0.13, 1.25, 0.14, size=6.9, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "TARGET WORKERS", 3.72, 5.50, 1.61, 0.18, size=7, color=MUTED, bold=True, align=PP_ALIGN.CENTER)

    add_rect(slide, 0.88, 5.10, 2.41, 0.54, fill=PANEL, line=LINE)
    add_text(slide, "STATE AFTER EACH NODE", 1.04, 5.27, 2.09, 0.15, size=7.4, color=GREEN, bold=True, align=PP_ALIGN.CENTER)
    add_rect(slide, 3.74, 5.10, 1.55, 0.54, fill=PANEL, line=LINE)
    add_text(slide, "BOUNDED DATA RETRY", 3.86, 5.27, 1.31, 0.15, size=7.1, color=GOLD, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "Prototype: isolated graph + explicit state • Target: queue workers + backpressure", 0.88, 5.79, 4.44, 0.18, size=7.3, color=MUTED, align=PP_ALIGN.CENTER)

    # Business value on the right.
    add_text(slide, "VALUE HYPOTHESES • MEASURE IN PILOT", 6.72, 2.43, 3.10, 0.20, size=8.2, color=TEAL, bold=True)
    value_cards = [
        ("FASTER DECISIONS", "Target: parallel reviews", "p50 / p95 cycle time", TEAL),
        ("EXPERT CAPACITY", "Exceptions—not re-keying", "human touch-hours", GREEN),
        ("CONTROL CONSISTENCY", "One versioned policy", "concordance / defects", GOLD),
        ("AUDIT READINESS", "Reconstructable evidence trace", "packet reconstruction time", BLUE),
    ]
    for i, (label, action, measure, accent) in enumerate(value_cards):
        x = 6.70 + (i % 2) * 2.94
        y = 2.78 + (i // 2) * 1.56
        add_rect(slide, x, y, 2.69, 1.30, fill=PANEL, line=LINE)
        add_badge(slide, "", x + 0.18, y + 0.21, fill=accent, diameter=0.12)
        add_text(slide, label, x + 0.40, y + 0.16, 2.10, 0.20, size=8.2, color=accent, bold=True)
        add_text(slide, action, x + 0.18, y + 0.52, 2.27, 0.25, size=10.5, color=WHITE, bold=True)
        add_text(slide, "Measure: " + measure, x + 0.18, y + 0.92, 2.27, 0.18, size=7.5, color=MUTED)

    add_rect(slide, 6.70, 5.92, 5.63, 0.56, fill=PANEL_3, line="28516A")
    add_text(slide, "Design separates policy packs from prompts and model releases.", 6.93, 6.10, 5.17, 0.19, size=10, color=TEAL, bold=True, align=PP_ALIGN.CENTER)


def slide_roi_roadmap(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 5, "ROI + roadmap", "2:30–3:00")
    add_title(
        slide,
        "Earn autonomy one gate at a time.",
        "Begin in shadow mode, measure safety and value, then widen only the scopes that prove both.",
        title_size=30,
    )

    # ROI block.
    add_rect(slide, 0.58, 2.19, 5.16, 3.82, fill=PANEL_2, line=LINE)
    add_pill(slide, "ILLUSTRATIVE • NOT A TIAA FORECAST", 0.86, 2.43, 2.68, fill=DEEP_GOLD, line="765F2E", color=GOLD, size=7.3)
    add_text(slide, "$2.20M", 0.86, 2.94, 2.20, 0.54, size=30, color=TEAL, bold=True, font=TITLE_FONT)
    add_text(slide, "gross annual value", 0.88, 3.48, 2.20, 0.22, size=10, color=MUTED)
    add_text(slide, "$1.25M", 3.18, 2.94, 2.05, 0.54, size=30, color=WHITE, bold=True, font=TITLE_FONT)
    add_text(slide, "year-1 cost", 3.20, 3.48, 1.86, 0.22, size=10, color=MUTED)

    add_line(slide, 0.86, 3.91, 5.45, 3.91, color=LINE, width=0.8)
    add_text(slide, "75.8%", 0.86, 4.15, 1.73, 0.45, size=25, color=GOLD, bold=True, font=TITLE_FONT)
    add_text(slide, "year-1 ROI", 0.88, 4.63, 1.73, 0.20, size=9, color=MUTED)
    add_text(slide, "5.7 mo", 3.18, 4.15, 1.73, 0.45, size=25, color=GREEN, bold=True, font=TITLE_FONT)
    add_text(slide, "simplified payback", 3.20, 4.63, 1.73, 0.20, size=9, color=MUTED)

    add_rect(slide, 0.86, 5.11, 4.58, 0.57, fill=PANEL, line=LINE_SOFT)
    add_text(slide, "5,000 cases × 8h × $95 × 55% + rework value", 1.06, 5.30, 4.18, 0.18, size=8.8, color=SOFT_WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, "Replace every assumption with shadow-pilot measurements.", 0.89, 5.79, 4.52, 0.17, size=7.8, color=MUTED, align=PP_ALIGN.CENTER)

    # Adoption staircase.
    add_text(slide, "PROPOSED MODULAR ADOPTION", 6.16, 2.43, 2.65, 0.20, size=8.5, color=TEAL, bold=True)
    phases = [
        ("0", "DISCOVER", "2 weeks", 0.00, LINE),
        ("1", "SHADOW", "4–6 weeks", 0.38, TEAL),
        ("2", "ASSISTED", "human final", 0.76, BLUE),
        ("3", "SCOPED", "low-risk only", 1.14, GOLD),
        ("4", "REUSE", "new policy packs", 1.52, GREEN),
    ]
    base_y = 5.35
    for i, (num, label, detail, lift, accent) in enumerate(phases):
        x = 6.15 + i * 1.23
        y = base_y - lift
        h = 0.78 + lift
        add_rect(slide, x, y, 1.08, h, fill=PANEL if i != 4 else DEEP_TEAL, line=accent)
        add_badge(slide, num, x + 0.12, y + 0.14, fill=accent, color=INK if accent != LINE else SOFT_WHITE, diameter=0.27, size=7.5)
        add_text(slide, label, x + 0.12, y + 0.36, 0.84, 0.16, size=6.6, color=accent if accent != LINE else MUTED, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, detail, x + 0.09, y + h - 0.20, 0.90, 0.16, size=6.2, color=MUTED, align=PP_ALIGN.CENTER)

    add_rect(slide, 6.15, 6.24, 6.16, 0.54, fill=PANEL_3, line="28516A")
    add_text(slide, "Target: faster decisions. Visible controls. Proof attached.", 6.46, 6.38, 5.54, 0.24, size=13.3, color=WHITE, bold=True, font=TITLE_FONT, align=PP_ALIGN.CENTER)


def slide_architecture(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 6, "Production target architecture", backup=True)
    add_title(
        slide,
        "One orchestration authority. Many bounded capabilities.",
        "Production target—not deployed locally: LangGraph lifecycle, Bedrock language and policy-as-code gates.",
        title_size=27,
    )
    add_pill(slide, "NOT DEPLOYED", 9.27, 0.34, 1.18, fill=DEEP_RED, line="753C45", color=RED, size=7.0)

    # Entry path.
    entry = [
        (0.58, "STREAMLIT / REACT", "guided intake"),
        (2.34, "API + IDENTITY", "gateway • SSO"),
        (4.10, "SQS", "backpressure"),
    ]
    for x, label, sub in entry:
        add_rect(slide, x, 2.33, 1.48, 0.84, fill=PANEL, line=LINE)
        add_text(slide, label, x + 0.10, 2.53, 1.28, 0.18, size=7.1, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, sub, x + 0.10, 2.81, 1.28, 0.16, size=6.8, color=MUTED, align=PP_ALIGN.CENTER)
    add_line(slide, 2.06, 2.75, 2.34, 2.75, color="486579")
    add_chevron(slide, 2.08, 2.58, color=MUTED, size=15)
    add_line(slide, 3.82, 2.75, 4.10, 2.75, color="486579")
    add_chevron(slide, 3.84, 2.58, color=MUTED, size=15)
    add_line(slide, 5.58, 2.75, 5.91, 2.75, color=TEAL)
    add_chevron(slide, 5.62, 2.58, color=TEAL, size=15)

    # Control plane.
    add_rect(slide, 5.92, 2.18, 4.43, 3.77, fill=PANEL_2, line=TEAL, line_width=1.25)
    add_text(slide, "LANGGRAPH CONTROL PLANE", 6.19, 2.39, 2.56, 0.20, size=9, color=TEAL, bold=True)
    add_pill(slide, "ECS / AGENTCORE ADAPTER", 8.39, 2.33, 1.66, fill=PANEL, line=LINE, color=MUTED, size=6.5)
    add_rect(slide, 6.19, 2.86, 1.18, 0.58, fill=PANEL, line=LINE)
    add_text(slide, "PREFLIGHT", 6.34, 3.06, 0.88, 0.14, size=7, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_line(slide, 7.37, 3.15, 7.65, 3.15, color="486579")
    add_chevron(slide, 7.38, 2.98, color=MUTED, size=13)
    add_rect(slide, 7.66, 2.86, 1.26, 0.58, fill=PANEL_3, line=TEAL)
    add_text(slide, "1 · ANALYST", 7.79, 3.06, 1.00, 0.14, size=7, color=TEAL, bold=True, align=PP_ALIGN.CENTER)

    specialist_y = [3.72, 4.34, 4.96]
    for (num, label, accent), yy in zip([("2", "COMPLIANCE", BLUE), ("3", "GOVERNANCE", GREEN), ("4", "FINANCE", GOLD)], specialist_y):
        add_rect(slide, 6.18, yy, 1.70, 0.46, fill=PANEL, line=accent)
        add_text(slide, f"{num} · {label}", 6.34, yy + 0.14, 1.38, 0.14, size=6.8, color=accent, bold=True, align=PP_ALIGN.CENTER)
        add_line(slide, 7.88, yy + 0.23, 8.23, yy + 0.23, color="486579", width=1.0)
    add_line(slide, 8.22, 3.15, 8.22, 5.19, color="486579", width=1.0)

    add_rect(slide, 8.52, 3.72, 1.53, 0.74, fill=PANEL, line=LINE)
    add_text(slide, "POLICY +\nRECONCILE", 8.69, 3.88, 1.19, 0.31, size=7.2, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_line(slide, 9.28, 4.46, 9.28, 4.70, color="486579")
    add_chevron(slide, 9.17, 4.51, color=MUTED, size=13)
    add_rect(slide, 8.52, 4.72, 1.53, 0.69, fill=PANEL_3, line=TEAL)
    add_text(slide, "5 · SPONSOR", 8.68, 4.98, 1.21, 0.14, size=7.2, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    add_pill(slide, "FINAL GATE → COMPLETE / HITL", 7.57, 5.52, 2.48, fill=DEEP_GOLD, line="765F2E", color=GOLD, size=6.8)

    # Supporting capabilities.
    support = [
        ("BEDROCK RUNTIME", "bounded narrative", TEAL),
        ("LAMBDA TOOLS", "allowlisted • read-mostly", BLUE),
        ("S3 / KNOWLEDGE", "evidence snapshot", GREEN),
        ("POSTGRES / DDB", "state + checkpoints", GOLD),
    ]
    for i, (label, detail, accent) in enumerate(support):
        y = 2.25 + i * 0.85
        add_rect(slide, 10.73, y, 2.03, 0.66, fill=PANEL, line=LINE)
        add_badge(slide, "", 10.91, y + 0.18, fill=accent, diameter=0.12)
        add_text(slide, label, 11.18, y + 0.12, 1.39, 0.18, size=7.1, color=WHITE, bold=True)
        add_text(slide, detail, 11.18, y + 0.36, 1.39, 0.16, size=6.6, color=MUTED)

    # Cross-cutting audit and observability.
    add_rect(slide, 0.58, 6.24, 12.18, 0.44, fill=PANEL_3, line="28516A")
    add_text(slide, "LOCAL → TARGET", 0.83, 6.38, 1.02, 0.13, size=6.6, color=TEAL, bold=True)
    add_text(slide, "JSONL + SHA-256 chain → production S3 Object Lock", 1.77, 6.36, 4.52, 0.17, size=8.2, color=SOFT_WHITE)
    add_text(slide, "Target: CloudWatch • OpenTelemetry • cost / latency / safety metrics", 7.23, 6.36, 5.18, 0.17, size=7.8, color=MUTED, align=PP_ALIGN.RIGHT)


def slide_failures(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 7, "Failure + hallucination controls", backup=True)
    add_title(
        slide,
        "Assume hallucinations. Remove their authority.",
        "Every risky output must survive provenance, schema, deterministic checks and a bounded route.",
        title_size=28,
    )

    # Fail-closed control loop.
    flow = [
        ("UNTRUSTED\nINPUT", RED),
        ("HASHED\nEVIDENCE", TEAL),
        ("CODE\nVALIDATION", BLUE),
        ("RETRY ≤2", GOLD),
        ("HUMAN /\nSAFE STOP", GREEN),
    ]
    fx = [0.62, 3.10, 5.58, 8.06, 10.54]
    for i in range(4):
        add_line(slide, fx[i] + 1.85, 2.67, fx[i + 1], 2.67, color="486579", width=1.3)
        add_chevron(slide, fx[i] + 1.98, 2.50, color=MUTED, size=15)
    for x, (label, accent) in zip(fx, flow):
        add_rect(slide, x, 2.27, 1.85, 0.83, fill=PANEL, line=accent)
        add_text(slide, label, x + 0.17, 2.46, 1.51, 0.36, size=7.9, color=accent, bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    risks = [
        ("BLANK", "Invented missing fee", "typed null + source hash", "retrieve twice → review"),
        ("INJX", "Prompt injection", "input scanner + boundary", "isolate content → human"),
        ("STALE", "Wrong / stale rule", "hash + effective date", "safe stop → approved pack"),
        ("CONFX", "Conflicting values", "field reconciliation", "preserve both → escalate"),
        ("UNITS", "Math / unit error", "Decimal + basis points", "ignore prose arithmetic"),
        ("AUDIT", "Audit commit fails", "hash-chain verification", "no final recommendation"),
    ]
    for i, (code, risk, detect, response) in enumerate(risks):
        x = 0.62 + (i % 3) * 4.10
        y = 3.48 + (i // 3) * 1.34
        add_rect(slide, x, y, 3.80, 1.12, fill=PANEL_2, line=LINE)
        add_pill(slide, code, x + 0.17, y + 0.17, 0.68, fill=DEEP_RED if code in {"BLANK", "INJX", "CONFX"} else PANEL, line="753C45" if code in {"BLANK", "INJX", "CONFX"} else LINE, color=RED if code in {"BLANK", "INJX", "CONFX"} else MUTED, size=6.8)
        add_text(slide, risk, x + 1.02, y + 0.19, 2.56, 0.20, size=9.5, color=WHITE, bold=True)
        add_text(slide, "DETECT", x + 0.18, y + 0.62, 0.55, 0.14, size=6.3, color=TEAL, bold=True)
        add_text(slide, detect, x + 0.78, y + 0.59, 1.23, 0.18, size=7.4, color=MUTED)
        add_text(slide, "RESPOND", x + 2.07, y + 0.62, 0.62, 0.14, size=6.3, color=GOLD, bold=True)
        add_text(slide, response, x + 2.66, y + 0.59, 0.94, 0.29, size=7.1, color=MUTED)

    add_rect(slide, 0.62, 6.24, 12.02, 0.42, fill=PANEL_3, line="28516A")
    add_rich_line(
        slide,
        [
            ("Five agents agreeing is not evidence. ", GOLD, 9.5, True, BODY_FONT),
            ("Independence comes from approved sources, deterministic tools and labeled adversarial cases.", SOFT_WHITE, 9.5, False, BODY_FONT),
        ],
        0.89,
        6.32,
        11.48,
        0.22,
        align=PP_ALIGN.CENTER,
    )


def slide_hitl_qa(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, 8, "Exact HITL gates + Q&A", backup=True)
    add_title(
        slide,
        "Autonomy is earned by explicit gates.",
        "Demo defaults are configurable illustrative policy—not statements of law.",
        title_size=28,
    )

    # Exact auto and human gate cards.
    add_rect(slide, 0.58, 2.14, 3.11, 4.34, fill=DEEP_TEAL, line="2D8C74")
    add_text(slide, "AUTO-COMPLETE WORKFLOW", 0.85, 2.39, 2.31, 0.23, size=9.3, color=GREEN, bold=True, font=TITLE_FONT)
    add_text(slide, "ALL must pass", 0.85, 2.73, 1.73, 0.20, size=8, color=MUTED, bold=True)
    auto_items = [
        "Recommendation = APPROVE",
        "Confidence ≥ 0.90",
        "Risk ≤ 24 / 100",
        "> 5 bps from internal cap",
        "No hard stop / missing / conflict / injection",
        "All agent + audit events committed",
    ]
    add_bullets(slide, auto_items, 0.87, 3.13, 2.48, 2.80, size=10.2, color=SOFT_WHITE, bullet_color=GREEN, gap=0.46)
    add_pill(slide, "RECOMMENDATION ONLY", 0.87, 5.99, 2.48, fill=PANEL_2, line="2D6E62", color=GREEN, size=7.4)

    add_rect(slide, 3.91, 2.14, 3.54, 4.34, fill=DEEP_GOLD, line="7E6A31")
    add_text(slide, "HUMAN REVIEW", 4.18, 2.39, 1.78, 0.23, size=10, color=GOLD, bold=True, font=TITLE_FONT)
    add_text(slide, "ANY one triggers", 4.18, 2.73, 1.73, 0.20, size=8, color=MUTED, bold=True)
    human_items = [
        "Any non-APPROVE recommendation",
        "Confidence < 0.85*",
        "Risk ≥ 40 / 100",
        "Fee within ±5 bps",
        "Missing after 2 / 2 retries",
        "Conflict, product scope or injection",
        "Hard stop or positive sales load",
    ]
    add_bullets(slide, human_items, 4.20, 3.13, 2.95, 3.10, size=9.5, color=SOFT_WHITE, bullet_color=GOLD, gap=0.39)
    add_text(slide, "*0.85–0.89 cannot auto-complete; routing remains policy-controlled.", 4.20, 6.05, 2.89, 0.25, size=6.9, color=MUTED)

    # Judge Q&A.
    add_text(slide, "TOP JUDGE QUESTIONS", 7.80, 2.20, 2.44, 0.20, size=8.5, color=TEAL, bold=True)
    qa = [
        (
            "01  How do you prevent hallucinations?",
            "We do not promise zero hallucinations. Typed nulls, source hashes, schema gates and deterministic math make model prose non-authoritative.",
            TEAL,
        ),
        (
            "02  Is this truly autonomous?",
            "The prototype autonomously prepares, tests, retries and routes a recommendation; it does not execute a financial decision.",
            GOLD,
        ),
        (
            "03  How does it scale safely?",
            "Today: isolated in-memory case state and bounded retry. Target: durable state and queue workers—after shadow safety and value gates pass.",
            GREEN,
        ),
    ]
    for i, (question, answer, accent) in enumerate(qa):
        y = 2.58 + i * 1.28
        add_rect(slide, 7.80, y, 4.83, 1.08, fill=PANEL_2, line=LINE)
        add_text(slide, question, 8.03, y + 0.16, 4.38, 0.21, size=9, color=accent, bold=True)
        add_text(slide, answer, 8.03, y + 0.46, 4.33, 0.45, size=8.5, color=SOFT_WHITE)
    add_rect(slide, 7.80, 6.40, 4.83, 0.30, fill=TEAL, line=None, radius=True)
    add_text(
        slide,
        "DEMO: ENTERED ID + REASON + ATTESTATION  •  REJECT→APPROVE: DISTINCT 2ND ID",
        7.97,
        6.47,
        4.49,
        0.16,
        size=6.8,
        color=INK,
        bold=True,
        align=PP_ALIGN.CENTER,
    )


def build_deck() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    prs.core_properties.title = "Fiducia — Five bounded agents. One evidence chain."
    prs.core_properties.subject = "ASU / TIAA AI Investment Spark Challenge — 3-minute pitch"
    prs.core_properties.author = "Fiducia Hackathon Team"
    prs.core_properties.keywords = "agentic AI, fund governance, AWS Bedrock, LangGraph, human in the loop"
    prs.core_properties.comments = "Educational prototype using synthetic data and illustrative policy."

    slide_problem(prs)
    slide_agents(prs)
    slide_demo(prs)
    slide_value_scale(prs)
    slide_roi_roadmap(prs)
    slide_architecture(prs)
    slide_failures(prs)
    slide_hitl_qa(prs)
    return prs


def main() -> None:
    prs = build_deck()
    prs.save(OUTPUT)

    # Re-open the actual artifact so generation fails loudly if the package is corrupt.
    reopened = Presentation(OUTPUT)
    if len(reopened.slides) != 8:
        raise RuntimeError(f"Expected 8 slides, found {len(reopened.slides)}")
    if tuple(round(value / 914400, 3) for value in (reopened.slide_width, reopened.slide_height)) != (13.333, 7.5):
        raise RuntimeError("Deck is not 16:9 widescreen")
    print(f"Generated {OUTPUT} ({len(reopened.slides)} slides, 16:9)")


if __name__ == "__main__":
    main()
