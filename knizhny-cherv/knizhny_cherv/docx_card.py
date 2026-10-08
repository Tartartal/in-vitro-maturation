"""Карточка Прозектора в .docx."""

from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape

from knizhny_cherv.prozektor import (
    BUCKET_EMPTY,
    BUCKET_LEAD,
    BUCKET_TITLE,
    BUCKETS,
    LANGUAGE_NAME,
    Prozektor,
    Quote,
    how_to,
)

_COLS = (
    ("#", 700),
    ("Раздел", 2200),
    ("Цитата", 7200),
    ("Ссылки", 5036),
)
_TABLE_WIDTH = sum(width for _, width in _COLS)


def write_docx(path, prozektor: Prozektor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    link_ids = _link_ids(ref.href for quote in prozektor.quotes for ref in quote.refs)
    document = _document_xml(prozektor, link_ids)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _RELS)
        archive.writestr("word/_rels/document.xml.rels", _doc_rels(link_ids))
        archive.writestr("word/styles.xml", _STYLES)
        archive.writestr("word/document.xml", document)


def _document_xml(prozektor: Prozektor, link_ids: dict[str, str]) -> str:
    document = prozektor.document
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">',
        "<w:body>",
        _p(f"Прозектор: {document.title}", bold=True, size=32, center=True, after=80),
        _p("Цитаты дословные и на языке статьи. Английский не переводится.", size=22, after=40),
        _p(
            "В столбце «Ссылки» стоят пункты списка литературы этой статьи, на которые опирается фраза.",
            size=22,
            after=160,
        ),
    ]
    if document.authors:
        parts.append(_p(f"Авторы: {document.authors}", size=22, after=40))
    if document.year:
        parts.append(_p(f"Год: {document.year}", size=22, after=40))
    if document.doi:
        parts.append(_p(f"DOI: {document.doi}", size=22, after=40))
    source = document.source or "—"
    parts.append(_p(f"Источник: {source}", size=22, after=40))
    if source.startswith("PMC") and source[3:].isdigit():
        parts.append(_p(f"https://europepmc.org/articles/{source}", size=22, after=40))
    language = LANGUAGE_NAME.get(document.language, document.language)
    parts.append(_p(f"Язык цитат: {language}", size=22, after=40))
    parts.append(_p(f"Охват: {document.completeness}", size=22, after=40))
    parts.append(_p(f"Прочитано предложений: {prozektor.sentences_seen}", size=22, after=200))

    for bucket in BUCKETS:
        parts.append(_p(BUCKET_TITLE[bucket], bold=True, size=28, after=60, before=240))
        parts.append(_p(BUCKET_LEAD[bucket], size=22, italic=True, after=80))
        rows = prozektor.by_bucket(bucket)
        if not rows:
            parts.append(_p(BUCKET_EMPTY[bucket], size=22, after=80))
            continue
        if bucket == "protocol":
            parts.append(_protocols(rows, link_ids))
            continue
        parts.append(_table(rows, link_ids))
    parts.append(
        "<w:sectPr>"
        '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
        '<w:pgMar w:top="851" w:right="851" w:bottom="851" w:left="851" '
        'w:header="400" w:footer="400" w:gutter="0"/>'
        "</w:sectPr>"
    )
    parts.append("</w:body></w:document>")
    return "".join(parts)


def _protocols(rows: list[Quote], link_ids: dict[str, str]) -> str:
    groups: list[tuple[str, list[Quote]]] = []
    for quote in rows:
        if not groups or groups[-1][0] != quote.section:
            groups.append((quote.section, []))
        groups[-1][1].append(quote)
    parts: list[str] = []
    for section, quotes in groups:
        title, body = how_to(section)
        parts.append(_p(title, bold=True, size=24, before=160, after=40))
        parts.append(_p(body, size=22, after=80))
        for index, quote in enumerate(quotes, start=1):
            parts.append(_p(f"{index}. {quote.text}", size=20, after=20))
            parts.append(_ref_paragraph(quote, link_ids, prefix="Ссылки: "))
    return "".join(parts)


def _table(rows: list[Quote], link_ids: dict[str, str]) -> str:
    header = "".join(_cell_text(title, width, header=True) for title, width in _COLS)
    body = []
    for index, quote in enumerate(rows, start=1):
        values = (
            _cell_text(str(index), _COLS[0][1]),
            _cell_text(quote.section, _COLS[1][1]),
            _cell_text(quote.text, _COLS[2][1]),
            _cell_refs(quote, _COLS[3][1], link_ids),
        )
        body.append("<w:tr>" + "".join(values) + "</w:tr>")
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _, width in _COLS)
    borders = (
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="B7B7B7"/>'
        "</w:tblBorders>"
    )
    return (
        "<w:tbl><w:tblPr>"
        f'<w:tblW w:w="{_TABLE_WIDTH}" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/>'
        f"{borders}"
        '<w:tblCellMar>'
        '<w:top w:w="40" w:type="dxa"/>'
        '<w:left w:w="80" w:type="dxa"/>'
        '<w:bottom w:w="40" w:type="dxa"/>'
        '<w:right w:w="80" w:type="dxa"/>'
        "</w:tblCellMar>"
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>"
        '<w:tr><w:trPr><w:tblHeader/></w:trPr>'
        f"{header}</w:tr>"
        + "".join(body)
        + "</w:tbl>"
    )


def _cell_text(text: str, width: int, *, header: bool = False) -> str:
    return _cell_body(width, header, [_text_paragraph(text, header=header)])


def _cell_refs(quote: Quote, width: int, link_ids: dict[str, str]) -> str:
    if not quote.refs:
        return _cell_text("—", width)
    return _cell_body(width, False, [_ref_paragraph(quote, link_ids)])


def _ref_paragraph(quote: Quote, link_ids: dict[str, str], *, prefix: str = "") -> str:
    if not quote.refs:
        return _p((prefix or "Ссылки: ") + "—", size=18, after=80)
    runs: list[str] = [_run(prefix)] if prefix else []
    for index, ref in enumerate(quote.refs):
        if index:
            runs.append(_run("; "))
        label = f"{ref.label}. {ref.text}".strip()
        runs.append(_run(label + (" " if ref.href else "")))
        if ref.href:
            runs.append(_hyperlink(ref.href, link_ids[ref.href]))
    return (
        "<w:p><w:pPr>"
        '<w:spacing w:before="0" w:after="80" w:line="240" w:lineRule="auto"/>'
        '<w:ind w:left="360"/>'
        "</w:pPr>"
        + "".join(runs)
        + "</w:p>"
    )


def _cell_body(width: int, header: bool, paragraphs: list[str]) -> str:
    fill = ' w:fill="1F4E79"' if header else ""
    shade = f'<w:shd w:val="clear" w:color="auto"{fill}/>' if header else ""
    return (
        "<w:tc>"
        f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
        + "".join(paragraphs)
        + "</w:tc>"
    )


def _text_paragraph(text: str, *, header: bool) -> str:
    color = '<w:color w:val="FFFFFF"/>' if header else ""
    bold = "<w:b/>" if header else ""
    return (
        "<w:p><w:pPr>"
        '<w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/>'
        "</w:pPr>"
        + _run(text, bold=bold, color=color)
        + "</w:p>"
    )


def _run(text: str, *, bold: str = "", color: str = "") -> str:
    return (
        "<w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        f"{bold}{color}"
        '<w:sz w:val="20"/><w:szCs w:val="20"/>'
        "</w:rPr>"
        f'<w:t xml:space="preserve">{_xml(text)}</w:t>'
        "</w:r>"
    )


def _hyperlink(href: str, rel_id: str) -> str:
    return (
        f'<w:hyperlink r:id="{rel_id}" w:history="1">'
        "<w:r><w:rPr>"
        '<w:rStyle w:val="Hyperlink"/>'
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        '<w:color w:val="0563C1"/><w:u w:val="single"/>'
        '<w:sz w:val="20"/><w:szCs w:val="20"/>'
        "</w:rPr>"
        f'<w:t xml:space="preserve">{_xml(href)}</w:t>'
        "</w:r></w:hyperlink>"
    )


def _link_ids(hrefs) -> dict[str, str]:
    ids: dict[str, str] = {}
    number = 2
    for href in hrefs:
        if href and href not in ids:
            ids[href] = f"rId{number}"
            number += 1
    return ids


def _doc_rels(link_ids: dict[str, str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
    ]
    for href, rel_id in link_ids.items():
        lines.append(
            f'<Relationship Id="{rel_id}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
            f'Target="{_xml(href)}" TargetMode="External"/>'
        )
    lines.append("</Relationships>")
    return "".join(lines)


def _p(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    size: int = 22,
    center: bool = False,
    before: int = 0,
    after: int = 80,
) -> str:
    align = '<w:jc w:val="center"/>' if center else ""
    return (
        "<w:p><w:pPr>"
        f"{align}"
        f'<w:spacing w:before="{before}" w:after="{after}" w:line="276" w:lineRule="auto"/>'
        "</w:pPr><w:r><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>'
        + ("<w:b/>" if bold else "")
        + ("<w:i/>" if italic else "")
        + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
        "</w:rPr>"
        f'<w:t xml:space="preserve">{_xml(text)}</w:t>'
        "</w:r></w:p>"
    )


def _xml(text: str) -> str:
    cleaned = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    return escape(cleaned)


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr>
  </w:style>
</w:styles>
"""
