"""One-off script: render docs/PROJECT_HANDBOOK.md to docs/PROJECT_HANDBOOK.pdf.

Not part of the daily pipeline -- run manually whenever the handbook markdown
changes. Uses `markdown` (pure Python, already available) + `xhtml2pdf`
(pure Python, pip-installed for this task) instead of pandoc/wkhtmltopdf/
weasyprint, none of which are installed on this machine and would require a
system-level toolchain (LaTeX, cairo/pango, or a browser engine) to add.
"""
import re
import shutil
from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "PROJECT_HANDBOOK.md"
PDF_PATH = ROOT / "docs" / "PROJECT_HANDBOOK.pdf"
# Copy of /Library/Fonts/Arial Unicode.ttf under a space-free path -- xhtml2pdf's
# own font loader (context.py's atFontFace/loadFont, which populates its
# *own* fontList used at render time -- registering with reportlab's global
# pdfmetrics directly does NOT reach it) silently no-ops on a src url() it
# can't resolve, and a %20-escaped space in the original path tripped that.
# Confirmed by direct source read of xhtml2pdf/context.py, not guessed.
# Not committed to git (23MB, gitignored, a system-font copy) -- recreated
# on demand below rather than requiring it to be pre-staged.
FONT_SYSTEM_SRC = Path("/Library/Fonts/Arial Unicode.ttf")
FONT_REGULAR = ROOT / "scratch" / "fonts" / "ArialUnicode.ttf"
if not FONT_REGULAR.exists():
    FONT_REGULAR.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FONT_SYSTEM_SRC, FONT_REGULAR)

FONT_FACE_CSS = (
    '@font-face { font-family: "ArialUnicode"; src: url("'
    + FONT_REGULAR.as_posix()
    + '"); }'
)

CSS = FONT_FACE_CSS + """
@page {
    size: A4;
    margin: 2cm 1.7cm;
    @frame footer_frame {
        -pdf-frame-content: footer_content;
        bottom: 1cm; margin-left: 1.7cm; margin-right: 1.7cm; height: 1cm;
    }
}
body { font-family: "ArialUnicode", "Helvetica", sans-serif; font-size: 9.5pt; line-height: 1.35; }
h1 { font-size: 16pt; margin-top: 22px; margin-bottom: 8px; border-bottom: 1.5pt solid #333333; padding-bottom: 4px; }
h2 { font-size: 12.5pt; margin-top: 16px; margin-bottom: 6px; color: #1a1a1a; }
h3 { font-size: 10.5pt; margin-top: 10px; }
p { margin: 4px 0; text-align: justify; }
a { color: #1a4faa; text-decoration: none; }
/* table-layout: fixed forces every column to the same share of the page
   width regardless of content -- without it, a long unbroken inline-code
   path in one cell (e.g. a report filename) pushed that whole column wider
   than the page and got clipped at the margin instead of wrapping. */
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 7.6pt; table-layout: fixed; }
th, td { border: 0.5pt solid #999999; padding: 3px 4px; text-align: left; vertical-align: top; word-break: break-all; }
th { background-color: #e8e8e8; font-weight: bold; }
/* ArialUnicode first (not just Courier New): several code/pre blocks mix
   Vietnamese prose with ASCII commands (Phần 3.5's template, facts_summary.txt
   excerpts) -- Courier New has no Vietnamese diacritics, so those rendered as
   missing-glyph boxes. Trades exact monospace column alignment for correctness. */
code { font-family: "ArialUnicode", "Courier New", monospace; font-size: 8.5pt; background-color: #f2f2f2; padding: 0 2px; word-break: break-all; }
pre { font-family: "ArialUnicode", "Courier New", monospace; font-size: 7.8pt; background-color: #f2f2f2; padding: 6px; white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; }
blockquote { margin: 6px 0 6px 10px; padding: 4px 8px; border-left: 3pt solid #999999; color: #333333; }
img { max-width: 100%; }
hr { border: none; border-top: 0.5pt solid #999999; margin: 10px 0; }
"""

FOOTER_HTML = '<div id="footer_content" style="text-align:center; font-size:8pt; color:#666;">Sổ tay dự án vietnam-quant-research — trang <pdf:pagenumber/> / <pdf:pagecount/></div>'


def add_soft_breaks_in_table_cells(html: str) -> str:
    """xhtml2pdf/reportlab's table-cell Paragraph wrapping only breaks at a
    real whitespace character -- confirmed empirically with an isolated test
    table outside this document: neither CSS word-break/overflow-wrap/
    table-layout:fixed NOR a U+200B zero-width-space entity created a break
    point, but an ordinary space did. A long unbroken run (a report file
    path with no spaces) in a table cell was clipped at the page margin
    instead of wrapping. Fix, scoped to <td> only (leaves command blocks in
    Phụ lục D copy-paste-clean): insert a real space after '/' -- a visible
    tradeoff (a little extra gap) in exchange for not losing the tail of the
    citation off the page edge. Deliberately NOT breaking on '_' too: a first
    attempt did, and it fragmented short column-name identifiers throughout
    every table (e.g. "final_score" -> "final_ score") for no benefit, since
    '/' alone already gives report paths (the actual overflowing content)
    a break point every 10-20 characters."""

    def add_spaces(text):
        return re.sub(r"(/)(?=[^\s])", r"\1 ", text)

    def repl(m):
        return "<td" + m.group(1) + ">" + add_spaces(m.group(2)) + "</td>"

    return re.sub(r"<td([^>]*)>(.*?)</td>", repl, html, flags=re.DOTALL)


def link_callback(uri: str, rel: str) -> str:
    """xhtml2pdf resource resolver: relative image paths in the .md are
    relative to docs/ (where the .md lives) -- resolve to a plain absolute
    filesystem path (xhtml2pdf's image loader wants a path/plain URL, not a
    file:// URI)."""
    if uri.startswith(("http://", "https://")):
        return uri
    abs_path = (MD_PATH.parent / uri).resolve()
    return str(abs_path)


def main():
    md_text = MD_PATH.read_text(encoding="utf-8")
    # Arial Unicode has no glyph for U+26A0/U+FE0F (warning emoji) -- renders
    # as a missing-glyph box in the PDF specifically. The .md keeps the real
    # emoji (renders fine in GitHub/editors); only this PDF rendering path
    # substitutes a plain-text tag consistent with the doc's own
    # [chưa xác minh]/[suy luận] bracket convention.
    md_text = md_text.replace("⚠️", "[CẢNH BÁO]")
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )
    body_html = add_soft_breaks_in_table_cells(body_html)

    full_html = f"""<html><head><meta charset="utf-8">
<style>{CSS}</style>
</head><body>
{FOOTER_HTML}
{body_html}
</body></html>"""

    with open(PDF_PATH, "wb") as out:
        result = pisa.CreatePDF(
            full_html,
            dest=out,
            encoding="utf-8",
            link_callback=link_callback,
        )
    if result.err:
        raise SystemExit(f"xhtml2pdf reported {result.err} error(s)")
    print(f"Wrote {PDF_PATH} ({PDF_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
