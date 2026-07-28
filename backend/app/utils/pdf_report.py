"""Render a final migration report (dict) to a PDF, in memory."""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

GREEN = colors.HexColor("#16A34A")
AMBER = colors.HexColor("#D97706")
RED = colors.HexColor("#DC2626")
GRID = colors.HexColor("#E5E7EB")
HEAD_BG = colors.HexColor("#F3F4F6")

SEVERITY_COLORS = {
    "high": colors.HexColor("#DC2626"),
    "medium": colors.HexColor("#D97706"),
    "low": colors.HexColor("#2563EB"),
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], fontSize=20, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], spaceBefore=14, spaceAfter=6),
        "body": ParagraphStyle("b", parent=base["BodyText"], fontSize=10, leading=14),
        "muted": ParagraphStyle("m", parent=base["BodyText"], fontSize=9,
                                textColor=colors.HexColor("#6B7280")),
    }


def _table_style() -> TableStyle:
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, GRID),
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])


def _grid_table(s: dict[str, Any], header: list[str], data_rows: list[list[str]],
                col_widths: list[float]) -> Table:
    rows = [[Paragraph(f"<b>{h}</b>", s["body"]) for h in header]]
    for r in data_rows:
        rows.append([Paragraph(str(c), s["body"]) for c in r])
    t = Table(rows, colWidths=col_widths)
    t.setStyle(_table_style())
    return t


def _page_chrome(job: dict[str, Any], generated_at: str):
    """Migrate wordmark + job timestamp on every page, page number in footer."""
    def draw(canvas, doc):  # noqa: ANN001 — reportlab callback signature
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(GREEN)
        canvas.roundRect(18 * mm, h - 11 * mm, 6 * mm, 6 * mm, 1.4 * mm,
                         stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawCentredString(21 * mm, h - 9.2 * mm, "M")
        canvas.setFillColor(colors.HexColor("#111827"))
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(26 * mm, h - 9.4 * mm, "Migrate")
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 18 * mm, h - 9.4 * mm,
                               f"{job.get('name', '')} · {generated_at} UTC")
        canvas.setLineWidth(0.5)
        canvas.setStrokeColor(GRID)
        canvas.line(18 * mm, h - 12.5 * mm, w - 18 * mm, h - 12.5 * mm)
        canvas.drawCentredString(w / 2, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def render_report_pdf(job: dict[str, Any], report: dict[str, Any],
                      semantic: dict[str, Any] | None = None,
                      confidence_breakdown: dict[str, Any] | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=22 * mm, bottomMargin=16 * mm,
                            title=f"Migration report — {job.get('name', '')}")
    s = _styles()
    story: list[Any] = []

    score = report.get("confidence_score", 0)
    passed = report.get("passed", False)

    # ── Cover page ───────────────────────────────────────────────────
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph("Migration Report", s["title"]))
    story.append(Paragraph(job.get("name", ""), ParagraphStyle(
        "cover_sub", fontSize=15, leading=20, spaceAfter=18,
        textColor=colors.HexColor("#374151"))))
    cover_rows = [
        ["Source", str(job.get("source_db_type", "?"))],
        ["Target", str(job.get("target_db_type", "?"))],
        ["Job ID", str(job.get("id", "—"))],
        ["Generated",
         f"{str(report.get('generated_at', ''))[:19].replace('T', ' ')} UTC"],
        ["Rows migrated", f"{job.get('rows_migrated', 0):,}"],
        ["Confidence", f"{score}/100 — {'PASSED' if passed else 'NEEDS REVIEW'}"],
    ]
    cover = Table([[Paragraph(f"<b>{k}</b>", s["body"]), Paragraph(v, s["body"])]
                   for k, v in cover_rows], colWidths=[45 * mm, 115 * mm])
    cover.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(cover)
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Generated by Migrate — semantic database migration. Every column was "
        "profiled against real sampled data, not just its declared type.",
        s["muted"]))
    story.append(PageBreak())

    story.append(Paragraph("Migration Report", s["title"]))
    story.append(Paragraph(
        f"{job.get('name', '')} · {job.get('source_db_type', '?')} → "
        f"{job.get('target_db_type', '?')} · generated "
        f"{str(report.get('generated_at', ''))[:19].replace('T', ' ')} UTC", s["muted"]))
    story.append(Spacer(1, 6))

    verdict = "PASSED" if passed else "NEEDS REVIEW"
    verdict_color = colors.HexColor("#16A34A") if passed else colors.HexColor("#D97706")
    head = Table([[Paragraph(f"<b>Confidence score: {score}/100</b>", s["body"]),
                   Paragraph(f"<b><font color='#{verdict_color.hexval()[2:]}'>"
                             f"{verdict}</font></b>", s["body"])]],
                 colWidths=[100 * mm, 60 * mm])
    head.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#E5E7EB")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(head)

    story.append(Paragraph("Executive summary", s["h2"]))
    story.append(Paragraph(report.get("executive_summary", "—"), s["body"]))

    if semantic:
        story.append(Paragraph("Semantic mismatch report card", s["h2"]))
        summ = semantic.get("summary", {})
        story.append(Paragraph(
            f"Schema trust score: <b>{semantic.get('schema_trust_score', 0)}/100</b> — "
            f"{summ.get('total_mismatches', 0)} mismatch(es) across "
            f"{summ.get('total_columns_profiled', 0)} profiled columns.", s["body"]))
        story.append(Spacer(1, 4))
        sem_rows = []
        for b in semantic.get("implicit_booleans", []):
            sem_rows.append([f"{b['table']}.{b['column']}", "Implicit boolean",
                             b.get("declared_type") or "?",
                             ", ".join(b.get("sample_values", [])),
                             f"{b.get('confidence', 0)}%"])
        for e in semantic.get("implicit_enums", []):
            vals = ", ".join(e.get("distinct_values", [])[:5])
            if e.get("distinct_count", 0) > 5:
                vals += " …"
            sem_rows.append([f"{e['table']}.{e['column']}", "Implicit enum",
                             e.get("declared_type") or "?", vals,
                             f"{e.get('confidence', 0)}%"])
        for n in semantic.get("never_null_nullables", []):
            sem_rows.append([f"{n['table']}.{n['column']}", "Never-null nullable",
                             n.get("declared_type") or "?",
                             f"0 nulls in {n.get('sample_size', 0)} rows", "—"])
        for p in semantic.get("pii_columns", []):
            sem_rows.append([f"{p['table']}.{p['column']}", "Suspected PII",
                             p.get("declared_type") or "?",
                             p.get("pii_type", "other"), "—"])
        if sem_rows:
            story.append(_grid_table(
                s, ["Column", "Finding", "Declared", "Evidence", "Confidence"],
                sem_rows, [42 * mm, 30 * mm, 26 * mm, 44 * mm, 18 * mm]))
        else:
            story.append(Paragraph(
                "No semantic mismatches detected — the schema means what it says.",
                s["body"]))

    plan = job.get("migration_plan") or {}
    if plan.get("tables"):
        story.append(Paragraph("Migration plan summary", s["h2"]))
        if plan.get("summary"):
            story.append(Paragraph(str(plan["summary"]), s["body"]))
            story.append(Spacer(1, 4))
        story.append(_grid_table(
            s, ["Source table", "Target", "Columns", "Warnings"],
            [[t.get("source_table", ""), t.get("target_table_name", ""),
              str(len(t.get("column_mappings", []))),
              "; ".join(t.get("warnings", [])) or "—"]
             for t in plan["tables"]],
            [40 * mm, 40 * mm, 18 * mm, 62 * mm]))

    validation = job.get("validation_report") or {}
    if validation.get("tables"):
        story.append(Paragraph("Validation results", s["h2"]))
        story.append(_grid_table(
            s, ["Table", "Source rows", "Target rows", "Hash match", "FK ok"],
            [[t, str(v.get("source_rows", "")), str(v.get("target_rows", "")),
              f"{(v.get('sample_hash') or {}).get('match_ratio', 1.0):.0%}",
              "yes" if v.get("fk_integrity_ok") else "NO"]
             for t, v in validation["tables"].items()],
            [50 * mm, 28 * mm, 28 * mm, 28 * mm, 26 * mm]))

    if confidence_breakdown:
        story.append(Paragraph("Confidence breakdown", s["h2"]))
        story.append(_grid_table(
            s, ["Table", "Confidence", "Columns under 90%"],
            [[t["table"], f"{t['confidence']}%",
              ", ".join(c["column"] for c in t["columns"]
                        if c["needs_review"]) or "—"]
             for t in confidence_breakdown.get("tables", [])],
            [50 * mm, 26 * mm, 84 * mm]))

    ce = report.get("confidence_explanation") or {}
    story.append(Paragraph("Why the confidence score is what it is", s["h2"]))
    if ce.get("narrative"):
        story.append(Paragraph(ce["narrative"], s["body"]))
        story.append(Spacer(1, 4))
    breakdown = ce.get("breakdown") or []
    if breakdown:
        rows = [[Paragraph("<b>Check</b>", s["body"]), Paragraph("<b>Weight</b>", s["body"]),
                 Paragraph("<b>Score</b>", s["body"]), Paragraph("<b>Reason</b>", s["body"])]]
        for b in breakdown:
            rows.append([Paragraph(str(b.get("component", "")), s["body"]),
                         Paragraph(str(b.get("weight", "")), s["body"]),
                         Paragraph(str(b.get("score", "")), s["body"]),
                         Paragraph(str(b.get("reason", "")), s["body"])])
        t = Table(rows, colWidths=[35 * mm, 18 * mm, 16 * mm, 91 * mm])
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)

    story.append(Paragraph("Flags — what you should check", s["h2"]))
    flags = report.get("flags") or []
    if not flags:
        story.append(Paragraph("No flags. All validation checks passed cleanly.", s["body"]))
    for f in flags:
        sev = str(f.get("severity", "low")).lower()
        color = SEVERITY_COLORS.get(sev, SEVERITY_COLORS["low"])
        table_part = f" · table <b>{f.get('table')}</b>" if f.get("table") else ""
        story.append(Paragraph(
            f"<font color='#{color.hexval()[2:]}'><b>[{sev.upper()}]</b></font> "
            f"<b>{f.get('title', '')}</b>{table_part}", s["body"]))
        story.append(Paragraph(str(f.get("detail", "")), s["body"]))
        if f.get("what_to_check"):
            story.append(Paragraph(f"<i>Check:</i> {f['what_to_check']}", s["muted"]))
        story.append(Spacer(1, 6))

    recs = report.get("recommendations") or []
    if recs:
        story.append(Paragraph("Recommendations", s["h2"]))
        for r in recs:
            story.append(Paragraph(f"• {r}", s["body"]))

    story.append(Paragraph("Rolling this migration back", s["h2"]))
    story.append(Paragraph(
        "A rollback script for this job is available from the migration detail "
        "page, or directly at "
        f"<b>/api/v1/migrations/{job.get('id', '')}/rollback-script</b>. "
        "It drops the migrated tables in reverse dependency order.", s["body"]))
    story.append(Paragraph(
        "It is a manual guide, not an automatic rollback — review every "
        "statement before running it. Dropping these tables permanently "
        "deletes all migrated data.", s["muted"]))

    chrome = _page_chrome(
        job, str(report.get("generated_at", ""))[:19].replace("T", " "))
    doc.build(story, onFirstPage=chrome, onLaterPages=chrome)
    return buf.getvalue()
