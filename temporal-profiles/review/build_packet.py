#!/usr/bin/env python3
"""Build the reviewer PDF from the two adjacent Markdown documents.

Requires Python 3.8+ and ReportLab. This optional documentation build does not
change or execute the scientific solver, its corpus, or the native batch.
Run from any directory: python3 path/to/review/build_packet.py
"""

from pathlib import Path
import html
import re
from urllib.parse import urljoin

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, Preformatted, KeepTogether,
)


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "Goutam_Dyapa_Reviewer_Packet.pdf"
BASE_REF = "cc03ddb6454f00378fae2f5570144f741090fe87"
REPO = "https://github.com/gouthamdyapa/counterfactual-fraud-networks/"
BASE_URL = REPO + "blob/" + BASE_REF + "/temporal-profiles/review/"
NAVY = colors.HexColor("#142D45")
TEAL = colors.HexColor("#087E88")
INK = colors.HexColor("#253443")
MUTED = colors.HexColor("#536677")
PALE = colors.HexColor("#EFF5F7")
RULE = colors.HexColor("#CEDADF")
PAGE_WIDTH, PAGE_HEIGHT = A4
WIDTH = PAGE_WIDTH - 84

STYLES = {
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10.0,
                           leading=13.3, textColor=INK, spaceAfter=7.4),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=26,
                            leading=29, textColor=NAVY, spaceAfter=11,
                            keepWithNext=True),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=16,
                         leading=19, textColor=NAVY, spaceBefore=5,
                         spaceAfter=10, keepWithNext=True),
    "h3": ParagraphStyle("h3", fontName="Helvetica-Bold", fontSize=11.6,
                         leading=14.6, textColor=TEAL, spaceBefore=7,
                         spaceAfter=5.4, keepWithNext=True),
    "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.8,
                           leading=11.6, textColor=INK, spaceAfter=0),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.8,
                         leading=11.6, textColor=colors.white),
    "code": ParagraphStyle("code", fontName="Courier", fontSize=8.6,
                           leading=11.8, textColor=NAVY, leftIndent=10,
                           rightIndent=8, spaceBefore=3, spaceAfter=9),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=10,
                             leading=13.3, textColor=INK, leftIndent=13,
                             firstLineIndent=-10, spaceAfter=6.0),
}


def inline(value):
    """Translate the small, intentional inline Markdown subset used here."""
    saved = []

    def stash(markup):
        saved.append(markup)
        return "@@TOKEN{}@@".format(len(saved) - 1)

    def link(match):
        label, target = match.groups()
        if target == "Goutam_Dyapa_Reviewer_Packet.pdf":
            return label
        anchors = {"REVIEWER_GUIDE.md": "guide", "NOVELTY_COMPARISON.md": "comparison"}
        dest = "#" + anchors[target] if target in anchors else urljoin(BASE_URL, target)
        return stash('<a href="{}" color="#087E88">{}</a>'.format(
            html.escape(dest, quote=True), html.escape(label)))

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = re.sub(r"`([^`]+)`", lambda m: stash(
        '<font name="Courier" size="8.5">{}</font>'.format(html.escape(m.group(1)))), value)
    value = html.escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    for index, markup in enumerate(saved):
        value = value.replace("@@TOKEN{}@@".format(index), markup)
    return value


def column_widths(header):
    n = len(header)
    if n == 2:
        fractions = [0.23, 0.77] if header[0] in {"Item", "Artifact"} else [0.24, 0.76]
    elif n == 3:
        fractions = [0.34, 0.25, 0.41] if header[0].startswith("Claim") else [0.30, 0.35, 0.35]
    elif n == 4:
        fractions = [0.43, 0.20, 0.20, 0.17] if header[0] == "Outcome" else [0.22, 0.27, 0.25, 0.26]
    else:
        fractions = [1 / n] * n
    return [WIDTH * v for v in fractions]


def table(block):
    rows = [[c.strip() for c in line.strip().strip("|").split("|")] for line in block]
    rows = [r for r in rows if not all(re.fullmatch(r":?-+:?", c) for c in r)]
    cells = []
    for i, row in enumerate(rows):
        cells.append([Paragraph(inline(c), STYLES["th" if i == 0 else "cell"]) for c in row])
    result = Table(cells, colWidths=column_widths(rows[0]), repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6.0),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, NAVY),
        ("LINEBELOW", (0, 1), (-1, -1), 0.35, RULE),
    ]))
    return [result, Spacer(1, 9)]


def parse(path, anchor):
    lines = path.read_text(encoding="utf-8").splitlines()
    flow = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            i += 1
            continue
        if line == "<!-- pagebreak -->":
            flow.append(PageBreak())
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            flow.append(Preformatted("\n".join(code), STYLES["code"]))
            i += 1
            continue
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                block.append(lines[i])
                i += 1
            flow.extend(table(block))
            continue
        heading = re.match(r"^(#{1,3}) (.*)", line)
        if heading:
            level = len(heading.group(1))
            key = {1: "title", 2: "h2", 3: "h3"}[level]
            title = inline(heading.group(2))
            if level == 1:
                title = '<a name="{}"/>'.format(anchor) + title
            flow.append(Paragraph(title, STYLES[key]))
            i += 1
            continue
        bullet = re.match(r"^(- |\d+\. )(.*)", line)
        if bullet:
            prefix = "- " if bullet.group(1).startswith("-") else bullet.group(1)
            flow.append(Paragraph(inline(prefix + bullet.group(2)), STYLES["bullet"]))
            i += 1
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|<!--|- |\d+\. )", lines[i]):
            paragraph.append(lines[i])
            i += 1
        markup = "<br/>".join(inline(p) for p in paragraph) if any(p.endswith("  ") for p in paragraph[:-1]) else inline(" ".join(paragraph))
        flow.append(Paragraph(markup, STYLES["body"]))
    return flow


def decorate(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(TEAL)
    canvas.rect(0, PAGE_HEIGHT - 6, PAGE_WIDTH, 6, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.drawString(42, PAGE_HEIGHT - 27, "GOUTAM DYAPA  /  REVIEW COMPANION")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_WIDTH - 42, PAGE_HEIGHT - 27, "12 NOVEMBER 2026")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(42, 33, PAGE_WIDTH - 42, 33)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.6)
    canvas.drawString(42, 21, "Working manuscript: 5 November 2026  |  Author-side review aid")
    canvas.drawRightString(PAGE_WIDTH - 42, 21, "Page {}".format(doc.page))
    canvas.restoreState()


def main():
    document = BaseDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=42, rightMargin=42,
                              topMargin=46, bottomMargin=46,
                              title="Temporal Walk Profiles: Reviewer Guide and Novelty Comparison",
                              author="Goutam Dyapa",
                              subject="Author-side companion to the working manuscript of 5 November 2026")
    frame = Frame(42, 46, WIDTH, PAGE_HEIGHT - 92, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, id="body")
    document.addPageTemplates([PageTemplate(id="review", frames=[frame], onPage=decorate)])
    story = parse(HERE / "REVIEWER_GUIDE.md", "guide")
    story.append(PageBreak())
    story.extend(parse(HERE / "NOVELTY_COMPARISON.md", "comparison"))
    document.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    main()
