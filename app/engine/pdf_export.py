"""PDF export for diagnostic reports using reportlab."""
from __future__ import annotations

import io
import re
from html import escape
from typing import Any


def markdown_to_pdf(markdown_text: str, interventions: list[dict[str, Any]] | None = None) -> bytes:
    """Convert markdown report to PDF bytes."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError:
        return _fallback_simple_pdf(markdown_text)

    # Register Chinese font
    font_name = "Helvetica"
    for font_path in [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]:
        try:
            pdfmetrics.registerFont(TTFont("SimHei", font_path))
            font_name = "SimHei"
            break
        except Exception:
            continue

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=30 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"], fontName=font_name, fontSize=18, spaceAfter=16
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"], fontName=font_name, fontSize=13, spaceBefore=14, spaceAfter=6
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"], fontName=font_name, fontSize=10, leading=14, spaceAfter=4
    )
    bold_style = ParagraphStyle(
        "CustomBold", parent=body_style, fontName=font_name, fontSize=10
    )

    story: list[Any] = []

    # Parse markdown sections
    lines = markdown_text.split("\n")
    table_rows: list[list[str]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if table_rows:
                story.append(_build_table(table_rows, font_name))
                table_rows = []
            continue

        if stripped.startswith("|"):
            # Collect table rows
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if all(c.replace("-", "").replace(":", "") == "" for c in cells):
                continue  # Skip separator rows
            table_rows.append(cells)
            continue

        if table_rows:
            story.append(_build_table(table_rows, font_name))
            table_rows = []

        if stripped.startswith("# "):
            story.append(Paragraph(escape(stripped[2:]), title_style))
        elif stripped.startswith("## "):
            story.append(Paragraph(escape(stripped[3:]), heading_style))
        elif stripped.startswith("### "):
            story.append(Paragraph(escape(stripped[4:]), heading_style))
        elif stripped.startswith("---"):
            story.append(Spacer(1, 8))
        elif stripped.startswith("!["):
            # Skip embedded images (base64 charts)
            story.append(Paragraph("[图表见完整报告]", body_style))
        else:
            # Clean markdown formatting
            clean = escape(stripped)
            clean = re.sub(r"\*\*(.*?)\*\*", rf"<b>\1</b>", clean)
            clean = re.sub(r"\*(.*?)\*", rf"<i>\1</i>", clean)
            clean = re.sub(r"`(.*?)`", rf'<font color="blue">\1</font>', clean)
            story.append(Paragraph(clean, body_style))

    if table_rows:
        story.append(_build_table(table_rows, font_name))

    # Add intervention cards if available
    if interventions:
        story.append(Spacer(1, 16))
        story.append(Paragraph("推荐干预方案", heading_style))
        for item in interventions:
            label = escape(str(item.get("label", "")))
            reason = escape(str(item.get("reason", "")))
            effect = escape(str(item.get("expected_effect", "")))
            story.append(Paragraph(f"<b>{label}</b>: {reason}", body_style))
            if effect:
                story.append(Paragraph(f"预期效果: {effect}", body_style))

    doc.build(story)
    return buffer.getvalue()


def _build_table(rows: list[list[str]], font_name: str) -> Any:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Table, TableStyle

    cell_style = ParagraphStyle("Cell", fontName=font_name, fontSize=8, leading=11)
    header_style = ParagraphStyle("HeaderCell", fontName=font_name, fontSize=8, leading=11)

    # Convert to Paragraph objects for proper text wrapping
    table_data = []
    for i, row in enumerate(rows):
        style = header_style if i == 0 else cell_style
        table_data.append([Paragraph(escape(str(cell)), style) for cell in row])

    if not table_data:
        from reportlab.platypus import Spacer
        return Spacer(1, 1)

    col_count = max(len(row) for row in table_data)
    col_width = (170 * mm) / col_count

    table = Table(table_data, colWidths=[col_width] * col_count)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b6ef2")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _fallback_simple_pdf(markdown_text: str) -> bytes:
    """Fallback PDF generation using matplotlib when reportlab is not available."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.27, 11.69))  # A4 size
    ax.axis("off")

    # Simple text rendering
    lines = markdown_text.split("\n")
    y = 0.95
    for line in lines[:80]:  # Limit lines
        clean = re.sub(r"[#*`|]", "", line).strip()
        if not clean:
            y -= 0.01
            continue
        fontsize = 14 if clean.startswith("城市") else 10
        ax.text(0.05, y, clean[:90], fontsize=fontsize, transform=ax.transAxes, wrap=True)
        y -= 0.018
        if y < 0.05:
            break

    buffer = io.BytesIO()
    fig.savefig(buffer, format="pdf", bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()
