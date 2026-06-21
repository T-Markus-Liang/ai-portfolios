"""Render a Markdown report into a readable PDF.

The renderer is intentionally simple and dependency-light: it supports the
Markdown shapes used by the generated brief (headings, bullets, blockquotes,
tables, details tags, and paragraphs) and prioritizes Chinese readability.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from html import escape, unescape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
    "/usr/share/fonts/truetype/arphic/ukai.ttc",
]


def _register_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            pdfmetrics.registerFont(TTFont("ReportCJK", path))
            return "ReportCJK"
    return "Helvetica"


def _clean_inline(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"<summary>(.*?)</summary>", r"\1", text)
    text = re.sub(r"</?details>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return escape(text.strip())


def _table_from_rows(rows: list[str], styles: dict[str, ParagraphStyle]) -> Table:
    cells: list[list[Paragraph]] = []
    for row in rows:
        parts = [part.strip() for part in row.strip().strip("|").split("|")]
        cells.append([Paragraph(_clean_inline(part), styles["table"]) for part in parts])
    col_count = max(len(row) for row in cells)
    for row in cells:
        while len(row) < col_count:
            row.append(Paragraph("", styles["table"]))
    table = Table(cells, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _styles(font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=font,
            fontSize=20,
            leading=26,
            textColor=colors.HexColor("#111827"),
            spaceAfter=10,
            alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=font,
            fontSize=14.5,
            leading=20,
            textColor=colors.HexColor("#1E40AF"),
            spaceBefore=12,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName=font,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=5,
        ),
        "quote": ParagraphStyle(
            "quote",
            parent=base["BodyText"],
            fontName=font,
            fontSize=10,
            leading=15,
            leftIndent=8,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0,
            textColor=colors.HexColor("#374151"),
            backColor=colors.HexColor("#F8FAFC"),
            spaceBefore=4,
            spaceAfter=6,
        ),
        "table": ParagraphStyle(
            "table",
            parent=base["BodyText"],
            fontName=font,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#111827"),
        ),
    }


def render(input_path: Path, output_path: Path) -> None:
    font = _register_font()
    styles = _styles(font)
    story = []
    table_rows: list[str] = []

    def flush_table() -> None:
        nonlocal table_rows
        if len(table_rows) >= 2:
            filtered = [row for row in table_rows if not re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", row)]
            if len(filtered) >= 1:
                story.append(_table_from_rows(filtered, styles))
                story.append(Spacer(1, 6))
        table_rows = []

    for raw_line in input_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_table()
            story.append(Spacer(1, 4))
            continue
        if "|" in line and line.strip().startswith("|"):
            table_rows.append(line)
            continue
        flush_table()
        if line.startswith("# "):
            story.append(Paragraph(_clean_inline(line[2:]), styles["title"]))
            story.append(HRFlowable(width="100%", color=colors.HexColor("#E5E7EB"), thickness=0.8))
        elif line.startswith("## "):
            story.append(Paragraph(_clean_inline(line[3:]), styles["h2"]))
        elif line.startswith("> "):
            story.append(Paragraph(_clean_inline(line[2:]), styles["quote"]))
        elif line.strip() == "---":
            story.append(HRFlowable(width="100%", color=colors.HexColor("#E5E7EB"), thickness=0.8))
        elif line.startswith("- "):
            story.append(Paragraph("• " + _clean_inline(line[2:]), styles["body"]))
        elif line.startswith("<details") or line.startswith("</details>"):
            continue
        else:
            style = styles["small"] if line.startswith("_") and line.endswith("_") else styles["body"]
            story.append(Paragraph(_clean_inline(line.strip("_")), style))
    flush_table()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=input_path.stem,
        author="ai-portfolios",
    )
    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Markdown report path")
    parser.add_argument("--output", default=None, help="Output PDF path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 2
    output_path = Path(args.output) if args.output else input_path.with_suffix(".pdf")
    render(input_path, output_path)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
