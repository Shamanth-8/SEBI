"""
Render a CircularSpec into a PDF that looks like a real SEBI circular.

The layout mirrors the published format (letterhead, reference number on the
left, date on the right, addressee block, "Sub:", numbered clauses, signature
block) so the PDF text layer that pdfplumber extracts matches what the model was
trained on.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.lib import colors

from app.ml.corpus import CircularSpec

_styles = getSampleStyleSheet()

BODY = ParagraphStyle(
    "CircBody", parent=_styles["Normal"], fontName="Times-Roman", fontSize=10.5,
    leading=15, alignment=TA_JUSTIFY, spaceAfter=7,
)
CLAUSE = ParagraphStyle(
    "CircClause", parent=BODY, leftIndent=18, firstLineIndent=-18,
)
HEADING = ParagraphStyle(
    "CircHeading", parent=_styles["Normal"], fontName="Times-Bold", fontSize=11,
    leading=15, spaceBefore=10, spaceAfter=6,
)
LETTERHEAD = ParagraphStyle(
    "Letterhead", parent=_styles["Normal"], fontName="Times-Bold", fontSize=13,
    leading=17, alignment=1, spaceAfter=2,
)
SUBLETTERHEAD = ParagraphStyle(
    "SubLetterhead", parent=_styles["Normal"], fontName="Times-Roman", fontSize=8.5,
    leading=11, alignment=1, textColor=colors.HexColor("#333333"),
)
META = ParagraphStyle(
    "Meta", parent=_styles["Normal"], fontName="Times-Roman", fontSize=10, leading=14,
)
SUBJECT = ParagraphStyle(
    "Subject", parent=_styles["Normal"], fontName="Times-Bold", fontSize=11,
    leading=15, spaceBefore=8, spaceAfter=10,
)
SIGN = ParagraphStyle(
    "Sign", parent=BODY, alignment=0, spaceAfter=1,
)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Times-Roman", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(A4[0] / 2, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def render_circular_pdf(spec: CircularSpec, out_path: str | Path) -> Path:
    """Write the spec to `out_path` and return the path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=22 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=spec.subject, author="Securities and Exchange Board of India",
        subject=spec.reference,
    )

    flow: List = []

    # ── Letterhead ────────────────────────────────────────────────────────
    # (The Devanagari line of the real letterhead is omitted: the built-in Type 1
    # fonts have no Devanagari glyphs, so it lands in the text layer as garbage
    # and pollutes every downstream extraction.)
    flow.append(Paragraph("SECURITIES AND EXCHANGE BOARD OF INDIA", LETTERHEAD))
    flow.append(Paragraph(
        "SEBI Bhavan, Plot No. C4-A, 'G' Block, Bandra Kurla Complex, Bandra (East), "
        "Mumbai 400 051 &nbsp;|&nbsp; www.sebi.gov.in", SUBLETTERHEAD))
    flow.append(Spacer(1, 5))
    flow.append(HRFlowable(width="100%", thickness=1.1, color=colors.HexColor("#1a3a6b")))
    flow.append(Spacer(1, 10))

    # ── Reference / date row ──────────────────────────────────────────────
    ref_tbl = Table(
        [[Paragraph(f"<b>{spec.reference}</b>", META),
          Paragraph(spec.issue_date.strftime("%B %d, %Y"), META)]],
        colWidths=[doc.width * 0.62, doc.width * 0.38],
    )
    ref_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    flow.append(ref_tbl)
    flow.append(Spacer(1, 10))

    # ── Addressees ────────────────────────────────────────────────────────
    flow.append(Paragraph("To,", META))
    for a in spec.addressees:
        flow.append(Paragraph(a, ParagraphStyle("Addr", parent=META, leftIndent=14)))
    flow.append(Spacer(1, 6))

    flow.append(Paragraph(f"Sub: {spec.subject}", SUBJECT))
    flow.append(Paragraph("Madam / Sir,", BODY))

    # ── Preamble ──────────────────────────────────────────────────────────
    for i, p in enumerate(spec.preamble, start=1):
        flow.append(Paragraph(f"{i}. {p}", CLAUSE))

    # ── Numbered sections ─────────────────────────────────────────────────
    for sec in spec.sections:
        flow.append(Paragraph(sec.heading, HEADING))
        for c in sec.clauses:
            flow.append(Paragraph(f"{c.number} &nbsp;{c.text}", CLAUSE))

    # ── Closing ───────────────────────────────────────────────────────────
    flow.append(Spacer(1, 4))
    start = len(spec.sections) + 1
    for i, p in enumerate(spec.closing, start=start):
        flow.append(Paragraph(f"{i}. {p}", CLAUSE))

    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Yours faithfully,", SIGN))
    flow.append(Spacer(1, 18))
    flow.append(Paragraph("<b>General Manager</b>", SIGN))
    flow.append(Paragraph("Market Intermediaries Regulation and Supervision Department", SIGN))
    flow.append(Paragraph("Email: circulars@sebi.gov.in", SIGN))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return out_path


def render_plain_pdf(title: str, text: str, out_path: str | Path) -> Path:
    """Render an arbitrary (non-circular) document — used for negative test files."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4,
                            leftMargin=22 * mm, rightMargin=20 * mm,
                            topMargin=20 * mm, bottomMargin=20 * mm, title=title)
    flow = [Paragraph(title.replace("_", " ").title(), HEADING), Spacer(1, 6)]
    for para in text.split("\n\n"):
        flow.append(Paragraph(para.replace("\n", " "), BODY))
    doc.build(flow)
    return out_path
