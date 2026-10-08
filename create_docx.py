# -*- coding: utf-8 -*-
"""Create a minimal valid .docx without third-party packages."""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent / "In_vitro_maturation_overview.docx"

TITLE = "In vitro maturation (IVM): краткий обзор"
SUBTITLE = "Краткий обзор темы вспомогательных репродуктивных технологий (≈2 стр.)"

SECTIONS: list[tuple[str, list[str]]] = [
    (
        "1. Определение и биологическая суть",
        [
            "In vitro maturation (IVM) — метод вспомогательных репродуктивных технологий, при котором из яичника извлекают незрелые ооциты (как правило, на стадии герминального пузырька, GV) из антральных фолликулов малого диаметра и доводят их до метафазы II (MII) в условиях лабораторной культуры. В отличие от классического ЭКО, IVM предполагает отсутствие полноценной контролируемой овариальной стимуляции либо её существенное сокращение. Исторически клиническое применение у человека связано с работами начала 1990-х годов; с тех пор метод развивался как более щадящая альтернатива стандартному ЭКО для отдельных групп пациенток.",
            "Ключевая идея IVM — перенести финальные этапы созревания ооцита из организма в культуру. Для компетентности ооцита важны не только завершение мейоза, но и цитоплазматическое созревание, метаболическая поддержка и сохранение коммуникации кумулюс–ооцит. Именно эти процессы определяют последующую способность к оплодотворению, эмбриогенезу и наступлению беременности.",
        ],
    ),
    (
        "2. Клинические показания",
        [
            "Наиболее обоснованные показания к IVM включают высокий риск синдрома гиперстимуляции яичников (СГЯ), прежде всего у женщин с синдромом поликистозных яичников (СПКЯ) или поликистозоподобными яичниками и высоким антральным фолликулярным счётом. Дополнительно метод рассматривают при срочном сохранении фертильности перед гонадотоксичным лечением (онкофертильность), при синдроме резистентных яичников и в отдельных сложных случаях повторных неудач ВРТ, когда полноценная стимуляция нежелательна или малоэффективна.",
            "Практическая привлекательность IVM связана с уменьшением лекарственной нагрузки, меньшим числом инъекций и визитов мониторинга, снижением финансовой и эмоциональной нагрузки цикла, а также практически полным устранением умеренного и тяжёлого СГЯ по сравнению со стандартным ЭКО. Вместе с тем комитеты по репродуктивной медицине подчёркивают, что у части пациенток риск СГЯ сегодня успешно контролируется и современными протоколами ЭКО (антагонисты GnRH, триггер агонистом), поэтому выбор IVM должен быть индивидуальным.",
        ],
    ),
    (
        "3. Протоколы и лабораторные подходы",
        [
            "Существует несколько клинико-лабораторных вариантов IVM: без стимуляции; с коротким праймингом ФСГ; с праймингом ХГЧ; комбинированные схемы. В последние годы активно изучаются двухфазные (biphasic) системы и CAPA-/SPOM-подходы, в которых перед собственно созреванием ооцит проходит этап пре-IVM-инкубации, имитирующий физиологическую модуляцию мейоза. Оптимизация сред включает гормоны, факторы роста, антиоксиданты и улучшение условий поддержания комплекса кумулюс–ооцит; перспективны также 3D- и микрофлюидные платформы.",
            "После созревания ооцитов обычно выполняют ИКСИ, культивирование эмбрионов и, часто, криоконсервацию с последующим переносом в размороженном цикле — это позволяет развести во времени пункцию и перенос и улучшить эндометриальную синхронизацию.",
        ],
    ),
    (
        "4. Эффективность и безопасность",
        [
            "По совокупным данным, включая рандомизированные сравнения у женщин со СПКЯ, IVM обеспечивает выраженное снижение умеренного и тяжёлого СГЯ, однако показатели живорождения за цикл, как правило, ниже, чем при стандартном ЭКО. В одном крупном РКИ без гонадотропинов частота живорождения в горизонте 6 месяцев составила около 22% против примерно 51% при ЭКО; при этом СГЯ в группе IVM практически отсутствовал. Обзоры Cochrane указывают: эффект IVM на живорождение по сравнению с ЭКО остаётся неопределённым из-за разнородности протоколов, при этом повышается риск выкидыша на клиническую беременность, а снижение СГЯ подтверждается с высокой достоверностью. Неонатальные исходы в доступных сериях в целом сопоставимы с ожидаемыми для ВРТ, но требуются дальнейшие долгосрочные наблюдения.",
        ],
    ),
    (
        "5. Ограничения и перспективы",
        [
            "Главные ограничения IVM — более низкая компетентность части ооцитов, вариабельность протоколов между центрами и меньшая предсказуемость исходов относительно рутинного ЭКО. Перспективы связаны с стандартизацией biphasic/CAPA-IVM, улучшением сред и селекции фолликулов, а также с точным отбором пациенток, для которых выигрыш по безопасности и нагрузке цикла перевешивает возможное снижение эффективности. Таким образом, IVM уже является клинически значимой опцией ВРТ, особенно при высоком риске СГЯ и в онкофертильности, но пока остаётся специализированным, а не универсальным методом первой линии.",
        ],
    ),
]

SOURCES = [
    "1. ASRM Practice Committee. In vitro maturation: a committee opinion. Fertil Steril. 2021.",
    "2. Advances, Mechanisms, and Clinical Perspectives for the In Vitro Maturation of Human Oocytes. PMC / Int. J. Mol. Sci. (обзор).",
    "3. Zheng X. et al. IVM without gonadotropins versus IVF in PCOS: RCT. Human Reproduction. 2022.",
    "4. Cochrane Review. In vitro maturation in subfertile women with PCOS undergoing ART (обновления обзора).",
]


def p(text: str, style: str = "Normal") -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>'
        f'<w:jc w:val="both"/><w:ind w:firstLine="567"/>'
        f'<w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        f'w:cs="Times New Roman"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'
        f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def p_center(text: str, *, bold: bool = False, size: int = 28, italic: bool = False) -> str:
    rpr = (
        '<w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        'w:cs="Times New Roman"/>'
        + ("<w:b/>" if bold else "")
        + ("<w:i/>" if italic else "")
        + f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr>'
    )
    return (
        f'<w:p><w:pPr><w:jc w:val="center"/>'
        f'<w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr>'
        f"<w:r>{rpr}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def p_heading(text: str) -> str:
    return (
        '<w:p><w:pPr><w:jc w:val="left"/><w:ind w:firstLine="0"/>'
        '<w:spacing w:before="200" w:after="80" w:line="360" w:lineRule="auto"/></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        'w:cs="Times New Roman"/><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>'
        f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def p_source(text: str) -> str:
    return (
        '<w:p><w:pPr><w:jc w:val="left"/><w:ind w:firstLine="0"/>'
        '<w:spacing w:after="40" w:line="276" w:lineRule="auto"/></w:pPr>'
        '<w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
        'w:cs="Times New Roman"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
        f"<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"
    )


def build_document_xml() -> str:
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'mc:Ignorable="w14 wp14">',
        "<w:body>",
        p_center(TITLE, bold=True, size=32),
        p_center(SUBTITLE, italic=True, size=24),
    ]
    for heading, paras in SECTIONS:
        parts.append(p_heading(heading))
        for para in paras:
            parts.append(p(para))
    parts.append(p_heading("Основные источники"))
    for src in SOURCES:
        parts.append(p_source(src))
    # A4 page size in twips: 11906 x 16838; margins ~2.5 cm = 1418 twips
    parts.append(
        "<w:sectPr>"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1418" w:right="1418" w:bottom="1418" w:left="1418" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        '<w:cols w:space="708"/>'
        "<w:docGrid w:linePitch=\"360\"/>"
        "</w:sectPr>"
    )
    parts.append("</w:body></w:document>")
    return "".join(parts)


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
