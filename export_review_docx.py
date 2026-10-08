# -*- coding: utf-8 -*-
"""Export literature/REVIEW.md to a .docx without third-party packages."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "literature" / "REVIEW.md"
OUT = ROOT / "literature" / "IVM_literature_review.docx"

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")


def runs(text: str, *, size: int = 28, bold: bool = False, italic: bool = False) -> str:
    pieces: list[tuple[str, bool, bool, bool]] = []
    pos = 0
    for match in INLINE.finditer(text):
        if match.start() > pos:
            pieces.append((text[pos : match.start()], bold, italic, False))
        token = match.group(0)
        if token.startswith("**"):
            pieces.append((token[2:-2], True, italic, False))
        elif token.startswith("`"):
            pieces.append((token[1:-1], bold, italic, True))
        else:
            pieces.append((token[1:-1], bold, True, False))
        pos = match.end()
    if pos < len(text):
        pieces.append((text[pos:], bold, italic, False))
    if not pieces:
        pieces.append(("", bold, italic, False))
    out: list[str] = []
    for chunk, is_bold, is_italic, is_code in pieces:
        rpr = (
            "<w:rPr>"
            '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
            + ("<w:b/>" if is_bold else "")
            + ("<w:i/>" if is_italic else "")
            + (f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
            + ("<w:shd w:val=\"clear\" w:fill=\"F2F2F2\"/>" if is_code else "")
            + "</w:rPr>"
        )
        out.append(f"<w:r>{rpr}<w:t xml:space=\"preserve\">{escape(chunk)}</w:t></w:r>")
    return "".join(out)


def paragraph(
    text: str,
    *,
    size: int = 28,
    bold: bool = False,
    italic: bool = False,
    align: str = "both",
    before: int = 0,
    after: int = 120,
    first_line: int = 0,
    left: int = 0,
    hanging: int = 0,
) -> str:
    ind = f'<w:ind w:left="{left}" w:hanging="{hanging}" w:firstLine="{first_line}"/>'
    return (
        f'<w:p><w:pPr><w:jc w:val="{align}"/>'
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="360" w:lineRule="auto"/>'
        f"{ind}</w:pPr>{runs(text, size=size, bold=bold, italic=italic)}</w:p>"
    )


def table(rows: list[list[str]]) -> str:
    usable = 9070
    cols = max(len(row) for row in rows)
    width = usable // cols
    borders = "".join(
        f'<w:{edge} w:val="single" w:sz="4" w:space="0" w:color="666666"/>'
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    body = [
        "<w:tbl>",
        "<w:tblPr>",
        f'<w:tblW w:w="{usable}" w:type="dxa"/>',
        f"<w:tblBorders>{borders}</w:tblBorders>",
        '<w:tblLayout w:type="fixed"/>',
        "</w:tblPr>",
    ]
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
    body.append(f"<w:tblGrid>{grid}</w:tblGrid>")
    for index, row in enumerate(rows):
        body.append("<w:tr>")
        for cell in row:
            shade = '<w:shd w:val="clear" w:fill="EFEFEF"/>' if index == 0 else ""
            body.append(
                "<w:tc>"
                f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}'
                '<w:vAlign w:val="center"/></w:tcPr>'
                + paragraph(cell.strip(), size=22, bold=(index == 0), align="left", after=40, before=40)
                + "</w:tc>"
            )
        body.append("</w:tr>")
    body.append("</w:tbl>")
    body.append(paragraph("", after=80))
    return "".join(body)


def parse(markdown: str) -> str:
    lines = markdown.splitlines()
    parts: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                raw = lines[index].strip().strip("|")
                cells = [cell.strip() for cell in raw.split("|")]
                if not all(set(cell) <= set("-: ") for cell in cells):
                    rows.append(cells)
                index += 1
            parts.append(table(rows))
            continue
        if stripped.startswith("# "):
            parts.append(paragraph(stripped[2:], size=36, bold=True, align="center", after=200, before=0))
            index += 1
            continue
        if stripped.startswith("## "):
            parts.append(paragraph(stripped[3:], size=30, bold=True, align="left", before=280, after=80))
            index += 1
            continue
        if stripped.startswith("### "):
            parts.append(paragraph(stripped[4:], size=28, bold=True, italic=True, align="left", before=200, after=60))
            index += 1
            continue
        if stripped.startswith("- "):
            parts.append(paragraph(stripped[2:], align="left", left=420, hanging=280, after=60))
            index += 1
            continue
        numbered = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if numbered:
            parts.append(
                paragraph(
                    f"{numbered.group(1)}. {numbered.group(2)}",
                    align="left",
                    left=420,
                    hanging=420,
                    after=60,
                )
            )
            index += 1
            continue
        parts.append(paragraph(stripped, first_line=567))
        index += 1
    return "".join(parts)


def build_document_xml() -> str:
    body = parse(SRC.read_text(encoding="utf-8"))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + body
        + "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1418" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr></w:body></w:document>"
    )


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:sz w:val="28"/><w:szCs w:val="28"/>
    </w:rPr>
  </w:style>
</w:styles>
"""


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        zf.writestr("word/_rels/document.xml.rels", DOC_RELS)
        zf.writestr("word/styles.xml", STYLES)
        zf.writestr("word/document.xml", build_document_xml())
    print(f"Created: {OUT}")
    print(f"Size bytes: {OUT.stat().st_size}")


if __name__ == "__main__":
    main()
