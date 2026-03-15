"""
generate_report.py
──────────────────
Generates a clean PDF report from scored_jobs.json using ReportLab.

Report structure:
  - Cover page: title, candidate name, stats, date
  - One section per job: rank, score, title, company, fit summary,
    rationale, matched/missing skills, apply URL, contact email

Output: .tmp/job_report_YYYY-MM.pdf

Usage:
    python tools/generate_report.py
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

load_dotenv()

SCORED_JOBS_PATH = ".tmp/scored_jobs.json"
OUTPUT_DIR = os.getenv("REPORT_OUTPUT_DIR", ".tmp")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("generate_report")

# ── Colour palette ────────────────────────────────────────────────────────────
BLUE_DARK = colors.HexColor("#1a3a5c")
BLUE_MID = colors.HexColor("#2867B2")   # LinkedIn blue
GREEN = colors.HexColor("#2e7d32")
ORANGE = colors.HexColor("#e65100")
GREY_LIGHT = colors.HexColor("#f5f5f5")
GREY_MED = colors.HexColor("#9e9e9e")
WHITE = colors.white
BLACK = colors.black


def build_styles() -> dict:
    base = getSampleStyleSheet()
    s = {}

    s["title"] = ParagraphStyle(
        "title", fontSize=28, leading=34, textColor=WHITE,
        fontName="Helvetica-Bold", spaceAfter=6,
    )
    s["subtitle"] = ParagraphStyle(
        "subtitle", fontSize=13, leading=18, textColor=colors.HexColor("#cce0ff"),
        fontName="Helvetica", spaceAfter=4,
    )
    s["rank"] = ParagraphStyle(
        "rank", fontSize=11, leading=14, textColor=BLUE_MID,
        fontName="Helvetica-Bold",
    )
    s["job_title"] = ParagraphStyle(
        "job_title", fontSize=15, leading=19, textColor=BLUE_DARK,
        fontName="Helvetica-Bold", spaceAfter=2,
    )
    s["company"] = ParagraphStyle(
        "company", fontSize=11, leading=14, textColor=GREY_MED,
        fontName="Helvetica", spaceAfter=8,
    )
    s["fit_summary"] = ParagraphStyle(
        "fit_summary", fontSize=11, leading=15, textColor=BLUE_DARK,
        fontName="Helvetica-Oblique", spaceAfter=6,
        borderPad=6, backColor=colors.HexColor("#e8f0fe"),
        borderRadius=4,
    )
    s["body"] = ParagraphStyle(
        "body", fontSize=10, leading=14, textColor=BLACK,
        fontName="Helvetica", spaceAfter=4,
    )
    s["label"] = ParagraphStyle(
        "label", fontSize=9, leading=12, textColor=GREY_MED,
        fontName="Helvetica-Bold", spaceAfter=2, spaceBefore=6,
    )
    s["link"] = ParagraphStyle(
        "link", fontSize=9, leading=12, textColor=BLUE_MID,
        fontName="Helvetica", spaceAfter=4,
    )
    s["footer"] = ParagraphStyle(
        "footer", fontSize=8, leading=10, textColor=GREY_MED,
        fontName="Helvetica",
    )
    return s


def skill_badge(name: str, colour: colors.Color) -> Table:
    """A small coloured pill for a skill name."""
    cell = Paragraph(
        f'<font color="white">{name}</font>',
        ParagraphStyle("badge", fontSize=8, fontName="Helvetica", leading=10),
    )
    t = Table([[cell]], colWidths=None)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def skill_badges_row(skills: list[str], colour: colors.Color) -> Table | None:
    if not skills:
        return None
    cells = [[skill_badge(s, colour) for s in skills[:8]]]
    t = Table(cells, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def score_bar(score: int) -> Table:
    """A simple score badge: e.g.  87/100"""
    colour = GREEN if score >= 70 else (ORANGE if score >= 50 else GREY_MED)
    cell = Paragraph(
        f'<font color="white"><b>{score}/100</b></font>',
        ParagraphStyle("score_text", fontSize=13, fontName="Helvetica-Bold", leading=16),
    )
    t = Table([[cell]], colWidths=[2.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colour),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def build_cover(styles: dict, candidate_name: str, total_jobs: int, top_score: int, run_date: str) -> list:
    elements = []

    # Blue header band
    header_data = [[
        Paragraph("LinkedIn Job Match Report", styles["title"]),
        Paragraph(run_date, styles["subtitle"]),
    ]]
    header = Table(header_data, colWidths=[13 * cm, 5 * cm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(header)
    elements.append(Spacer(1, 1 * cm))

    stats_rows = [
        ["Candidate", candidate_name],
        ["Jobs evaluated", str(total_jobs)],
        ["Top match score", f"{top_score}/100"],
        ["Report generated", run_date],
    ]
    stats_table = Table(stats_rows, colWidths=[5 * cm, 13 * cm])
    stats_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("LEADING", (0, 0), (-1, -1), 16),
        ("TEXTCOLOR", (0, 0), (0, -1), BLUE_DARK),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GREY_LIGHT, WHITE]),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(stats_table)
    elements.append(PageBreak())
    return elements


def build_job_section(styles: dict, job: dict, rank: int) -> list:
    elements = []
    score = job.get("score", 0)

    # Header row: rank badge + score badge
    rank_para = Paragraph(f"#{rank}", styles["rank"])
    score_widget = score_bar(score)
    header_row = Table([[rank_para, score_widget]], colWidths=[15.5 * cm, 2.5 * cm])
    header_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_row)
    elements.append(Spacer(1, 2 * mm))

    # Title and company
    elements.append(Paragraph(job.get("title", "Unknown Title"), styles["job_title"]))
    company_loc = f"{job.get('company', '')}  ·  {job.get('location', '')}"
    if job.get("posted_date"):
        company_loc += f"  ·  {job['posted_date']}"
    elements.append(Paragraph(company_loc, styles["company"]))

    # Fit summary
    if job.get("fit_summary"):
        elements.append(Paragraph(job["fit_summary"], styles["fit_summary"]))

    # Score rationale
    if job.get("score_rationale"):
        elements.append(Paragraph("Why this match?", styles["label"]))
        elements.append(Paragraph(job["score_rationale"], styles["body"]))

    # Matched skills
    matched = job.get("matched_skills") or []
    if matched:
        elements.append(Paragraph("Matched skills", styles["label"]))
        badges = skill_badges_row(matched, GREEN)
        if badges:
            elements.append(badges)
        elements.append(Spacer(1, 2 * mm))

    # Missing skills
    missing = job.get("missing_skills") or []
    if missing:
        elements.append(Paragraph("Skills to develop", styles["label"]))
        badges = skill_badges_row(missing, ORANGE)
        if badges:
            elements.append(badges)
        elements.append(Spacer(1, 2 * mm))

    # Apply link
    apply_url = job.get("apply_url", "")
    if apply_url:
        elements.append(Paragraph("Apply", styles["label"]))
        elements.append(Paragraph(f'<link href="{apply_url}">{apply_url}</link>', styles["link"]))

    # Contact email
    if job.get("contact_email"):
        elements.append(Paragraph("Contact", styles["label"]))
        elements.append(Paragraph(job["contact_email"], styles["link"]))

    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=GREY_MED))
    elements.append(Spacer(1, 6 * mm))
    return elements


def _on_first_page(canvas, doc):
    pass


def _on_later_pages(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY_MED)
    canvas.drawString(2 * cm, 1.2 * cm, "LinkedIn Job Match Report")
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}"
    )
    canvas.restoreState()


def generate_report(
    scored_jobs_path: str = SCORED_JOBS_PATH,
    output_dir: str = OUTPUT_DIR,
    candidate_name: str = "",
) -> str:
    p = Path(scored_jobs_path)
    if not p.exists():
        raise FileNotFoundError(f"scored_jobs.json not found: {scored_jobs_path}")

    with open(p) as f:
        jobs = json.load(f)

    if not jobs:
        raise RuntimeError("scored_jobs.json is empty — no jobs to report.")

    # Try to get candidate name from master profile if not provided
    if not candidate_name:
        master_path = Path(".tmp/master_profile.json")
        if master_path.exists():
            with open(master_path) as f:
                master = json.load(f)
            candidate_name = master.get("identity", {}).get("full_name", "Candidate")
        else:
            candidate_name = "Candidate"

    run_date = datetime.now().strftime("%B %Y")
    filename = f"job_report_{datetime.now().strftime('%Y-%m')}.pdf"
    output_path = Path(output_dir) / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
    )

    elements = []
    top_score = jobs[0].get("score", 0) if jobs else 0
    elements += build_cover(styles, candidate_name, len(jobs), top_score, run_date)

    for rank, job in enumerate(jobs, 1):
        elements += build_job_section(styles, job, rank)

    doc.build(elements, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)

    log.info("PDF report saved: %s (%d jobs)", output_path, len(jobs))
    return str(output_path.resolve())


if __name__ == "__main__":
    path = generate_report()
    print(f"Report generated: {path}")
