"""Render a Markdown market brief into HTML and PDF.

Preferred path:
  Markdown -> styled HTML -> Playwright/Chromium PDF

Fallback path:
  Markdown -> simple ReportLab PDF

The LLM owns the report content. This script owns visual presentation so the
output stays deterministic and maintainable.
"""

from __future__ import annotations

import argparse
import re
import sys
from html import escape, unescape
from pathlib import Path

CSS = """
:root {
  --ink: #111827;
  --muted: #64748b;
  --line: #dbe3ef;
  --panel: #f8fafc;
  --blue: #1d4ed8;
  --blue-soft: #eff6ff;
  --amber: #92400e;
  --amber-soft: #fffbeb;
  --green: #166534;
  --green-soft: #f0fdf4;
}
@page { size: A4; margin: 16mm 14mm 18mm; }
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: white;
  font-family: "Noto Sans CJK SC", "Noto Sans CJK", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  font-size: 12px;
  line-height: 1.62;
}
.page {
  max-width: 900px;
  margin: 0 auto;
}
.cover {
  border-bottom: 2px solid var(--ink);
  padding-bottom: 14px;
  margin-bottom: 18px;
}
h1 {
  margin: 0 0 8px;
  font-size: 25px;
  line-height: 1.18;
  letter-spacing: 0;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.pill {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 9px;
  color: var(--muted);
  background: var(--panel);
  font-size: 10.5px;
}
h2 {
  margin: 18px 0 8px;
  padding: 6px 9px;
  color: var(--blue);
  background: var(--blue-soft);
  border-left: 4px solid var(--blue);
  font-size: 15px;
  line-height: 1.35;
  break-after: avoid;
}
p { margin: 6px 0; }
ul { margin: 6px 0 10px 0; padding: 0; list-style: none; }
li {
  position: relative;
  margin: 5px 0;
  padding-left: 15px;
}
li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--blue);
  font-weight: 700;
}
blockquote {
  margin: 10px 0;
  padding: 9px 11px;
  border-left: 4px solid var(--amber);
  background: var(--amber-soft);
  color: #3f2f19;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 9px 0 12px;
  font-size: 10.5px;
  break-inside: avoid;
}
th, td {
  border: 1px solid var(--line);
  padding: 6px 7px;
  vertical-align: top;
}
th {
  background: var(--panel);
  color: #0f172a;
  font-weight: 700;
}
tr:nth-child(even) td { background: #fcfdff; }
a { color: var(--blue); text-decoration: none; word-break: break-all; }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 1px 4px;
}
hr {
  border: 0;
  border-top: 1px solid var(--line);
  margin: 16px 0;
}
details {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 7px;
  margin: 8px 0;
  padding: 7px 9px;
  break-inside: avoid;
}
summary {
  font-weight: 700;
  color: #0f172a;
}
.source-index h2 {
  color: var(--green);
  background: var(--green-soft);
  border-left-color: var(--green);
}
.footer {
  margin-top: 20px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 10px;
}
"""


def _clean_inline(text: str) -> str:
    text = unescape(text.strip())
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    protected = []

    def protect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@HTML{len(protected) - 1}@@"

    text = re.sub(r"</?(?:strong|code|a)(?:\s+href=\"[^\"]+\")?>", protect, text)
    text = escape(text)
    for idx, raw in enumerate(protected):
        text = text.replace(f"@@HTML{idx}@@", raw)
    return text


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$", line))


def _render_table(rows: list[str]) -> str:
    filtered = [row for row in rows if not _is_table_separator(row)]
    if not filtered:
        return ""
    html = ["<table>"]
    for row_idx, row in enumerate(filtered):
        tag = "th" if row_idx == 0 else "td"
        cells = "".join(f"<{tag}>{_clean_inline(cell)}</{tag}>" for cell in _split_table_row(row))
        html.append(f"<tr>{cells}</tr>")
    html.append("</table>")
    return "\n".join(html)


def markdown_to_html(markdown: str) -> str:
    body: list[str] = []
    table_rows: list[str] = []
    in_list = False
    in_details = False
    in_source_index = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            close_list()
            rendered = _render_table(table_rows)
            if rendered:
                body.append(rendered)
            table_rows = []

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_table()
            close_list()
            continue
        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            table_rows.append(line)
            continue
        flush_table()

        if line.startswith("# "):
            close_list()
            title = _clean_inline(line[2:])
            body.append(f'<section class="cover"><h1>{title}</h1><div class="meta">')
        elif line.startswith("生成时间：") or line.startswith("窗口：") or line.startswith("数据源：") or line.startswith("新增推文：") or line.startswith("模型："):
            body.append(f'<span class="pill">{_clean_inline(line)}</span>')
        elif line.startswith("## "):
            close_list()
            if body and body[-1] == '<span class="pill">':
                body.append("</div></section>")
            heading = _clean_inline(line[3:])
            if "原始" in heading or "来源索引" in heading:
                in_source_index = True
                body.append('<section class="source-index">')
            body.append(f"<h2>{heading}</h2>")
        elif line.startswith("> "):
            close_list()
            body.append(f"<blockquote>{_clean_inline(line[2:])}</blockquote>")
        elif line.strip() == "---":
            close_list()
            body.append("<hr>")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_clean_inline(line[2:])}</li>")
        elif line.startswith("<details"):
            close_list()
            in_details = True
            body.append("<details>")
        elif line.startswith("</details>"):
            close_list()
            in_details = False
            body.append("</details>")
        elif line.startswith("<details><summary>"):
            close_list()
            in_details = True
            summary = re.sub(r"^<details><summary>(.*?)</summary>$", r"\1", line)
            body.append(f"<details><summary>{_clean_inline(summary)}</summary>")
        elif line.startswith("<summary>"):
            close_list()
            summary = re.sub(r"^<summary>(.*?)</summary>$", r"\1", line)
            body.append(f"<summary>{_clean_inline(summary)}</summary>")
        else:
            close_list()
            body.append(f"<p>{_clean_inline(line.strip('_'))}</p>")

    flush_table()
    close_list()
    if in_details:
        body.append("</details>")
    if in_source_index:
        body.append("</section>")

    # Close cover meta if it was opened and not explicitly closed.
    html_body = "\n".join(body).replace('<div class="meta">\n<h2>', '<div class="meta"></div></section>\n<h2>')
    if '<section class="cover">' in html_body and "</section>" not in html_body.split("<h2>", 1)[0]:
        html_body = html_body.replace("\n<h2>", "\n</div></section>\n<h2>", 1)
    return html_body


def render_html(input_path: Path, output_path: Path) -> None:
    markdown = input_path.read_text(encoding="utf-8")
    body = markdown_to_html(markdown)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(input_path.stem)}</title>
<style>{CSS}</style>
</head>
<body>
<main class="page">
{body}
<div class="footer">Generated by ai-portfolios · Markdown archived, PDF rendered from HTML/CSS</div>
</main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def render_pdf_with_playwright(html_path: Path, output_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1240, "height": 1754}, device_scale_factor=1)
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()


def render_pdf_fallback(input_path: Path, output_path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    styles["BodyText"].fontName = "STSong-Light"
    styles["Title"].fontName = "STSong-Light"
    story = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            story.append(Spacer(1, 6))
            continue
        style = styles["Title"] if line.startswith("# ") else styles["BodyText"]
        story.append(Paragraph(escape(re.sub(r"^#+\s*", "", line)), style))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(output_path), pagesize=A4).build(story)


def render(input_path: Path, output_path: Path, html_output: Path | None = None) -> Path:
    html_path = html_output or output_path.with_suffix(".html")
    render_html(input_path, html_path)
    try:
        render_pdf_with_playwright(html_path, output_path)
    except Exception as exc:
        print(f"WARN: HTML/Chromium PDF failed, using fallback: {exc}", file=sys.stderr)
        render_pdf_fallback(input_path, output_path)
    return html_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Markdown report path")
    parser.add_argument("--output", default=None, help="Output PDF path")
    parser.add_argument("--html-output", default=None, help="Output HTML path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        return 2
    output_path = Path(args.output) if args.output else input_path.with_suffix(".pdf")
    html_path = Path(args.html_output) if args.html_output else output_path.with_suffix(".html")
    render(input_path, output_path, html_path)
    print(output_path)
    print(html_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
