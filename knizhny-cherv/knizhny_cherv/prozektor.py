"""Прозектор: разбор статьи в таблицы дословных цитат.

Цитата — предложение из текста статьи без пересказа и без перевода.
Колонка «без ссылок» снимает только маркеры цитирования.
"""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

_DOT = "\u0001"

_ABBREV = (
    "et al.",
    "Figs.",
    "Fig.",
    "figs.",
    "fig.",
    "i.e.",
    "e.g.",
    "vs.",
    "cf.",
    "ca.",
    "Dr.",
    "Mr.",
    "Mrs.",
    "Prof.",
    "approx.",
    "St.",
    "No.",
    "Vol.",
    "pp.",
)

_BRACKET_CIT = re.compile(r"\s*\[\s*\d+\s*(?:\s*[\u2013\-–,]\s*\d+\s*)*\]")
_AUTHOR = r"[A-Z][A-Za-z'’\-]+"
_AUTHOR_YEAR_ONE = rf"{_AUTHOR}(?:\s+et al\.|\s+(?:and|&)\s+{_AUTHOR})?\s*,?\s*\d{{4}}[a-z]?"
_AUTHOR_YEAR = re.compile(rf"\s*\({_AUTHOR_YEAR_ONE}(?:\s*[;,]\s*{_AUTHOR_YEAR_ONE})*\)")
_PAREN_NUM = re.compile(r"\s*\(\s*\d{1,3}\s*(?:\s*[,;]\s*\d{1,3}\s*)*\)")

_BOILER = re.compile(
    r"(?i)("
    r"informed consent|"
    r"ethics committee|"
    r"institutional review board|"
    r"declaration of helsinki|"
    r"\bapproved by the\b|"
    r"presented as mean|"
    r"expressed as mean|"
    r"presented as median|"
    r"expressed as median|"
    r"presented as frequenc|"
    r"considered statistically significant|"
    r"all statistical analyses were performed|"
    r"statistical analyses were performed using|"
    r"distributional assumptions|"
    r"^keywords?\s*:|"
    r"^key words\s*:"
    r")"
)

_DOSE = re.compile(
    r"(?i)\b\d+(?:\.\d+)?(?:\s*[\u2013\-]\s*\d+(?:\.\d+)?)?\s*"
    r"(?:mIU|IU|UI|mM|µM|μM|uM|nM|mg/m[lL]|mg/day|µg/m[lL]|μg/m[lL]|ug/m[lL]|ng/m[lL]|"
    r"mmHg|°C|℃|µg|μg|ug|mg|МЕ/мл|мМЕ/мл)\b"
)
_TIME = re.compile(
    r"(?i)(?:\bfor\s+|\bв течение\s+)?\b\d+(?:\s*[\u2013\-]\s*\d+)?\s*"
    r"(?:hours|minutes|hrs|hr|min|h|ч)\b"
)
_PROTOCOL = re.compile(
    r"(?i)("
    r"incubat|cultured|culture medium|maturation medium|ivm medium|supplemented with|"
    r"aspiration pressure|\d+-gauge|were retrieved|was retrieved|retrieval was|"
    r"fertili[sz]ed|were denuded|vitrif|were warmed|were thawed|"
    r"\bpriming\b|was administered|were administered|triggering was|was triggered|"
    r"embryos were transferred|embryo transfer was|were injected|"
    r"\bCOCs?\b|oocyte retrieval was|without gonadotropin|"
    r"were transferred|was transferred|luteal support|endometrium was|was prepared|"
    r"культивир|инкубир|сред[аеуы]\s+созреван"
    r")"
)
_PROTOCOL_SOFT = re.compile(
    r"(?i)(\bfollicle\b|\bendometrial\b|\baspiration\b|\bneedle\b|\bmedium\b|"
    r"oocytes were|\bCOCs were\b|\bmm\b|\bgauge\b|\bhCG\b|\bFSH\b|\bLH\b|\bICSI\b|\bpunctured\b|"
    r"\bendometrium\b|\bprogesterone\b|\bdydrogesterone\b|\bestradiol\b|weeks of gestation)"
)

_CONTROL = re.compile(
    r"(?i)("
    r"\bcontrol groups?\b|\bcontrols were\b|\bmatched controls\b|"
    r"\bcontrol arms?\b|\bas controls\b|\bas a control\b|"
    r"\bcontrol oocytes\b|\bcontrol patients\b|\bcontrol cycles\b|"
    r"women in the control|in the control group|"
    r"\bcomparison group\b|\bplacebo group\b|\buntreated group\b|"
    r"\bwere matched\b.{0,80}\bto\b|"
    r"контрол\w*\s+групп|групп\w*\s+контрол|в качестве контроля|группа сравнения"
    r")"
)

_CITE = re.compile(r"\[\s*\d+\s*(?:[\u2013\-–,]\s*\d+\s*)*\]|\bet al\.")
_PRIOR = re.compile(
    r"(?i)\b(?:previously|previous studies|prior studies|has been shown|have been shown|"
    r"was first reported|were first reported|it is known|it has been|it remains|"
    r"studies have|the literature|according to|"
    r"ранее|было показано|по данным|и соавт|предыдущ)\b"
)

_PVAL = re.compile(r"(?i)\b[Pp]\s*(?:<\s*|=|>\s*|≤|≥)\s*\d")
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_FINDING = re.compile(
    r"(?i)\b(?:no cases|did not occur|eliminated|no significant difference|"
    r"significantly (?:higher|lower|increased|decreased|different|greater|reduced)|"
    r"was significantly|were significantly)\b"
)
_ENROLL = re.compile(r"(?i)\b(?:of the\s+\d[\d,]*|a total of\s+\d[\d,]*|met the inclusion)\b")
_POINTER = re.compile(
    r"(?i)\b(?:are|is|were|was)\s+(?:presented|illustrated|shown)\s+in\s+(?:table|fig(?:ure)?)\b"
)
_OWN_AIM = re.compile(
    r"(?i)\b(?:we aimed|we sought|we conducted|here we|we performed|we included|we enrolled)\b"
)
_CITED_PRIOR = re.compile(r"(?i)\b(?:previous|previously|et al|noted by|reported by|as recently)\b")

_EXP_STRONG = re.compile(
    r"(?i)("
    r"\bthis study\b|\bthe present study\b|\bin the present study\b|\bhere we\b|"
    r"\bwe aimed\b|\bwe sought\b|\bwe conducted\b|\bwe performed\b|\bwe included\b|"
    r"\bwe enrolled\b|\bwe recruited\b|\bwe collected\b|\bwe evaluated\b|"
    r"\bwe compared\b|\bwe cultured\b|\bwe measured\b|"
    r"\bour clinical strategy\b|\bshifted to prioritize\b|"
    r"\bwere randomized\b|\bwas randomized\b|\brandomly assigned\b|\brandomly allocated\b|"
    r"\bwere randomised\b|\bwas randomised\b|"
    r"\bretrospective cohort\b|\bprospective cohort\b|\brandomized controlled\b|"
    r"\brandomised controlled\b|"
    r"в настоящем исследовании|в данном исследовании|мы провели|целью исследования"
    r")"
)
_EXP_WEAK = re.compile(
    r"(?i)("
    r"\bparticipants were\b|\beligible participants\b|\binclusion criteria\b|\bexclusion criteria\b|"
    r"\bwere included\b|\bwere enrolled\b|\bwere recruited\b|\bwere matched\b|\bwere excluded\b|"
    r"\bstudy group\b|\btreatment group\b|\bcomprised\b|"
    r"\bprimary outcome\b|\bsecondary outcome\b|\bsecondary reproductive\b|"
    r"\bconducted at\b|\bfollow-up\b|"
    r"\baged\s+\d|\bdiagnosed with\b|"
    r"\bbetween\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|\d{4})\b|"
    r"\bn\s*=\s*\d|"
    r"\bdefined as\b|\bobservation period\b|"
    r"\bcomparisons were conducted\b|\bwere compared using\b|\banalysis was employed\b|"
    r"\banalyses were performed\b|\bsubgroup\b|\bkaplan-?meier\b|\blog-rank\b|"
    r"критерии включения|критерии исключения|были включены|основная группа|"
    r"первичн\w+\s+исход|ретроспективн|проспективн|рандомизир"
    r")"
)

_TOP_SECTION = re.compile(
    r"^(abstract|background|introduction|materials and methods|materials & methods|"
    r"patients and methods|methods|results|results and discussion|discussion|"
    r"conclusions?|references|bibliography|"
    r"аннотация|введение|материалы и методы|пациенты и методы|методы|результаты|"
    r"обсуждение|заключение|выводы|литература|список литературы|библиография)$"
)

_INLINE_LABEL = re.compile(
    r"(?i)^(background|introduction|methods|materials and methods|results|conclusions?|discussion|"
    r"введение|методы|результаты|обсуждение|выводы|заключение)\s*:\s+(.+)$"
)

_HEADING_HINTS = (
    "protocol",
    "procedure",
    "criteria",
    "outcome",
    "statistical",
    "population",
    "design",
    "протокол",
    "критери",
    "исход",
    "дизайн",
    "популяц",
)

BUCKETS = ("experiment", "control", "literature", "results", "protocol")

BUCKET_TITLE = {
    "experiment": "Структура эксперимента",
    "control": "Контроль",
    "literature": "Данные литобзора",
    "results": "Результаты",
    "protocol": "Протоколы",
}

BUCKET_LEAD = {
    "experiment": "Как авторы устроили свою работу: дизайн, кто вошёл, группы, какие исходы заданы, чем сравнивали на уровне плана.",
    "control": "Чем задано сравнение: контрольная группа, подобранные контроли, группа сопоставления.",
    "literature": "Положения, которые опираются на чужие работы. Это фразы из введения и обсуждения, а не список литературы в конце статьи.",
    "results": "Что авторы сообщают как наблюдение своей работы: частоты, различия, значения P, случаи.",
    "protocol": "Шаги, дозы, среды и сроки. Они вынуты из методов, даже если в статье стояли вперемешку с дизайном.",
}

BUCKET_EMPTY = {
    "experiment": "В тексте не выделены предложения об устройстве исследования.",
    "control": "Отдельное описание контроля не выделено.",
    "literature": "Фраз с чужими данными не выделено.",
    "results": "Числовых итогов этой работы не выделено.",
    "protocol": "Пошаговый протокол в тексте не выделен.",
}

LANGUAGE_NAME = {"en": "английский", "ru": "русский", "mixed": "смешанный", "und": "не определён"}

_SKIP_TITLES = {
    "acknowledgements",
    "acknowledgments",
    "abbreviations",
    "authors' contributions",
    "author contributions",
    "funding",
    "financial support",
    "data availability",
    "data availability statement",
    "availability of data and materials",
    "declarations",
    "ethics approval and consent to participate",
    "ethics approval",
    "consent for publication",
    "competing interests",
    "conflicts of interest",
    "conflict of interest",
    "footnotes",
    "contributor information",
    "references",
    "bibliography",
    "associated data",
    "supplementary material",
    "supplementary materials",
    "supporting information",
    "disclosure",
    "author details",
    "orcid ids",
    "keywords",
    "key words",
    "литература",
    "список литературы",
    "библиография",
    "благодарности",
    "финансирование",
    "конфликт интересов",
}

_SKIP_SEC_TYPE = {"ack", "glossary", "fn-group", "ref-list", "contrib-info", "associated-data"}

_SKIP_INLINE = {"fn", "fn-group"}


@dataclass(frozen=True)
class Block:
    section: str
    zone: str
    protocol_section: bool
    text: str


@dataclass
class Document:
    title: str
    language: str
    blocks: list[Block]
    full_text: str
    source: str = ""

    @property
    def completeness(self) -> str:
        zones = {block.zone for block in self.blocks}
        if "methods" in zones and "results" in zones:
            return "полный текст"
        return "фрагмент или аннотация"


@dataclass(frozen=True)
class Quote:
    bucket: str
    section: str
    text: str
    plain: str


@dataclass
class Prozektor:
    document: Document
    quotes: list[Quote]
    sentences_seen: int = 0

    def by_bucket(self, bucket: str) -> list[Quote]:
        return [quote for quote in self.quotes if quote.bucket == bucket]


def split_sentences(text: str) -> list[str]:
    """Разбить абзац на предложения, не режа десятичные дроби и Fig. / et al."""
    raw = " ".join(text.replace("\xa0", " ").split())
    if not raw:
        return []
    protected = re.sub(r"(?<=\d)\.(?=\d)", _DOT, raw)
    protected = re.sub(r"(?<![A-Za-z])([A-Z])\.(?=\s)", lambda match: match.group(1) + _DOT, protected)
    for abbr in _ABBREV:
        protected = protected.replace(abbr, abbr.replace(".", _DOT))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ«\"“])", protected)
    sentences: list[str] = []
    for part in parts:
        sentence = " ".join(part.replace(_DOT, ".").split()).strip()
        if sentence:
            sentences.append(sentence)
    return sentences


def strip_citations(text: str) -> str:
    """Убрать маркеры цитирования, не трогая слова и числа результата."""
    out = _AUTHOR_YEAR.sub("", text)
    out = _BRACKET_CIT.sub("", out)
    out = _PAREN_NUM.sub("", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    return " ".join(out.split())


def language_of(text: str) -> str:
    cyr = len(re.findall(r"[А-Яа-яЁё]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    if cyr == 0 and lat == 0:
        return "und"
    if cyr > 0 and lat > 0 and min(cyr, lat) > max(cyr, lat) * 0.25:
        return "mixed"
    if cyr > lat:
        return "ru"
    return "en"


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text))


def _norm_heading(title: str) -> str:
    text = title.strip().lower().replace("’", "'").replace("–", "-")
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", text)
    return text.rstrip(":").strip()


def _is_skip_title(title: str) -> bool:
    text = _norm_heading(title)
    if not text:
        return False
    if text in _SKIP_TITLES:
        return True
    return any(text.startswith(item) for item in _SKIP_TITLES if len(item) > 12)


def zone_for(title: str, parent: str) -> str:
    """Роль раздела: intro, methods, results, discussion, abstract, skip или роль родителя."""
    if _is_skip_title(title):
        return "skip"
    text = _norm_heading(title)
    if not text:
        return parent or "other"
    if text in {"abstract", "аннотация"}:
        return "abstract"
    if text in {"background", "introduction", "введение"} or text.startswith("introduction") or text.startswith("введение"):
        return "intro"
    if re.search(
        r"\b(materials and methods|materials & methods|patients and methods|methods|"
        r"материалы и методы|пациенты и методы|методы)\b",
        text,
    ):
        return "methods"
    if re.search(r"\b(results|результаты)\b", text):
        return "results"
    if re.search(r"\b(discussion|conclusions?|обсуждение|заключение|выводы)\b", text):
        return "discussion"
    if parent == "skip":
        return "skip"
    if any(key in text for key in ("protocol", "procedure", "oocyte retrieval", "embryo culture", "протокол")):
        if parent in {"", "other", "methods", "abstract"}:
            return "methods"
    return parent or "other"


def protocol_section(title: str, zone: str) -> bool:
    if zone != "methods":
        return False
    text = _norm_heading(title)
    keys = (
        "protocol",
        "procedure",
        "culture",
        "medium",
        "priming",
        "retrieval",
        "transfer",
        "vitrif",
        "stimulat",
        "fertil",
        "icsi",
        "laboratory",
        "протокол",
    )
    return any(key in text for key in keys)


def looks_like_results(text: str, zone: str) -> bool:
    if zone == "intro":
        return False
    if zone == "methods" and re.search(r"(?i)\b(outcome was|defined as|criteria)\b", text):
        return False
    if _PVAL.search(text) or _PERCENT.search(text):
        return zone in {"results", "discussion", "abstract", "other"}
    if zone == "results" and (_FINDING.search(text) or (_ENROLL.search(text) and re.search(r"\d", text))):
        return True
    if zone == "discussion" and _FINDING.search(text) and re.search(r"(?i)\b(we|our|this study)\b", text):
        return True
    return False


def looks_like_experiment(text: str, zone: str) -> bool:
    if _EXP_STRONG.search(text):
        return True
    return zone == "methods" and bool(_EXP_WEAK.search(text))


def classify(text: str, zone: str, *, protocol: bool) -> set[str]:
    """Вернуть корзины, в которые входит предложение. Пусто — предложение не про работу авторов и не про чужие данные."""
    if _words(text) < 6 or _BOILER.search(text) or _POINTER.search(text):
        return set()
    buckets: set[str] = set()
    is_protocol = zone == "methods" and bool(
        _DOSE.search(text)
        or _TIME.search(text)
        or _PROTOCOL.search(text)
        or (protocol and (_PROTOCOL_SOFT.search(text) or re.search(r"(?i)\bwere defined as\b", text)))
    )
    if re.search(r"(?i)\b(primary outcome|secondary outcome|secondary reproductive|observation period)\b", text):
        is_protocol = False
    # Порог вроде «1.6 mg/dL» внутри определения исхода — не шаг протокола.
    if re.search(r"(?i)\b(?:was|were) defined as\b", text) and not protocol:
        is_protocol = False
    is_results = looks_like_results(text, zone)
    if zone == "discussion" and is_results and (_CITE.search(text) or _CITED_PRIOR.search(text)):
        is_results = False
    is_experiment = looks_like_experiment(text, zone)
    if zone == "discussion" and is_experiment and not _OWN_AIM.search(text):
        is_experiment = False
    cited = bool(_CITE.search(text) or _PRIOR.search(text))
    is_literature = cited and (
        zone in {"intro", "discussion"} or (zone == "abstract" and not is_results and not is_experiment)
    )
    is_control = bool(_CONTROL.search(text)) and not is_results

    if is_protocol and not is_results:
        buckets.add("protocol")
    if is_results:
        buckets.add("results")
    if is_literature and (zone != "results" or _PRIOR.search(text)):
        buckets.add("literature")
    if is_experiment and "protocol" not in buckets and "results" not in buckets:
        buckets.add("experiment")
    if is_control and "results" not in buckets:
        buckets.add("control")
    return buckets


def prozektor_of(document: Document) -> Prozektor:
    quotes: list[Quote] = []
    seen: set[tuple[str, str]] = set()
    sentences_seen = 0
    for block in document.blocks:
        if block.zone == "skip":
            continue
        for sentence in split_sentences(block.text):
            sentences_seen += 1
            chosen = classify(sentence, block.zone, protocol=block.protocol_section)
            if not chosen:
                continue
            plain = strip_citations(sentence)
            for bucket in BUCKETS:
                if bucket not in chosen:
                    continue
                key = (bucket, sentence)
                if key in seen:
                    continue
                seen.add(key)
                quotes.append(Quote(bucket=bucket, section=block.section, text=sentence, plain=plain))
    return Prozektor(document=document, quotes=quotes, sentences_seen=sentences_seen)


def parse_article(text: str, *, source: str = "") -> Document:
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return parse_jats(text, source=source)
    return parse_plain(text, source=source)


def parse_plain(text: str, *, source: str = "") -> Document:
    title = ""
    blocks: list[Block] = []
    top = ""
    sub = ""
    zone = "other"
    proto = False
    buffer: list[str] = []

    def section_path() -> str:
        parts = [part for part in (top, sub) if part]
        return " → ".join(parts) if parts else "Текст"

    def flush() -> None:
        if not buffer or zone == "skip":
            buffer.clear()
            return
        paragraph = " ".join(" ".join(buffer).split())
        buffer.clear()
        if paragraph:
            blocks.append(Block(section=section_path(), zone=zone, protocol_section=proto, text=paragraph))

    def take_heading(heading: str, *, top_level: bool) -> None:
        nonlocal title, top, sub, zone, proto
        if top_level and not title and not _TOP_SECTION.match(_norm_heading(heading)) and not _is_skip_title(heading):
            title = heading.strip()
            return
        parent = zone
        mapped = zone_for(heading, parent if not _is_top(heading) else "")
        if _is_top(heading) or _is_skip_title(heading):
            top = heading.strip()
            sub = ""
            zone = mapped if mapped != "other" else zone_for(heading, "")
        else:
            if not top:
                top = heading.strip()
                sub = ""
            else:
                sub = heading.strip()
            zone = zone_for(heading, parent)
        if zone == "skip":
            proto = False
        else:
            proto = protocol_section(heading, zone)

    for raw_line in text.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            flush()
            continue
        inline = _INLINE_LABEL.match(line)
        if inline:
            flush()
            take_heading(inline.group(1), top_level=False)
            buffer.append(inline.group(2))
            flush()
            continue
        if _is_plain_heading(line):
            flush()
            heading, top_level = _heading_text(line)
            take_heading(heading, top_level=top_level)
            continue
        buffer.append(line)
    flush()
    full = "\n".join(block.text for block in blocks)
    if not title:
        title = _first_title(text)
    return Document(title=title or "Без названия", language=language_of(full), blocks=blocks, full_text=full, source=source)


def parse_jats(xml: str, *, source: str = "") -> Document:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise ValueError(f"это не XML статьи: {exc}") from exc
    article = root if _local(root.tag) == "article" else next((el for el in root.iter() if _local(el.tag) == "article"), root)
    title = ""
    for el in article.iter():
        if _local(el.tag) == "article-title":
            title = _clean(_element_text(el))
            break
    blocks: list[Block] = []
    for el in list(article):
        if _local(el.tag) == "front":
            for child in el.iter():
                if _local(child.tag) == "abstract":
                    _walk_sec(child, [], "abstract", blocks, abstract=True)
        elif _local(el.tag) == "body":
            for child in list(el):
                if _local(child.tag) == "sec":
                    _walk_sec(child, [], "other", blocks, abstract=False)
                elif _local(child.tag) == "p":
                    paragraph = _clean(_element_text(child))
                    if paragraph:
                        blocks.append(Block(section="Текст", zone="other", protocol_section=False, text=paragraph))
    full = "\n".join(block.text for block in blocks)
    return Document(
        title=title or "Без названия",
        language=language_of(full),
        blocks=blocks,
        full_text=full,
        source=source,
    )


def render_markdown(prozektor: Prozektor) -> str:
    document = prozektor.document
    lines = [
        f"# Прозектор: {document.title}",
        "",
        "Цитаты ниже выписаны дословно и оставлены на языке статьи. Английский текст не переводится.",
        "Колонка «Без ссылок» повторяет ту же фразу без маркеров `[1]`, `[9–11]` и `(Smith et al., 2020)`.",
        "Слова не заменяются. Если таких маркеров не было, в колонке стоит «—».",
        "",
        "Список литературы, благодарности, финансирование, декларации и подписи к рисункам Прозектор не включает.",
        "",
        f"- Источник: {document.source or '—'}",
        f"- Язык цитат: {LANGUAGE_NAME.get(document.language, document.language)}",
        f"- Охват: {document.completeness}",
        f"- Прочитано предложений: {prozektor.sentences_seen}",
        "",
    ]
    for bucket in BUCKETS:
        lines.append(f"## {BUCKET_TITLE[bucket]}")
        lines.append("")
        lines.append(BUCKET_LEAD[bucket])
        lines.append("")
        rows = prozektor.by_bucket(bucket)
        if not rows:
            lines.append(BUCKET_EMPTY[bucket])
            lines.append("")
            continue
        lines.append("| # | Раздел | Цитата | Без ссылок |")
        lines.append("|---:|---|---|---|")
        for index, quote in enumerate(rows, start=1):
            plain = "—" if quote.plain == quote.text else quote.plain
            lines.append(
                "| "
                + " | ".join(
                    (
                        str(index),
                        _cell(quote.section),
                        _cell(quote.text),
                        _cell(plain),
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path, prozektor: Prozektor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(prozektor), encoding="utf-8")


def write_quotes_csv(path, prozektor: Prozektor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("bucket", "section", "quote", "without_citations"),
        )
        writer.writeheader()
        for quote in prozektor.quotes:
            writer.writerow(
                {
                    "bucket": quote.bucket,
                    "section": quote.section,
                    "quote": quote.text,
                    "without_citations": quote.plain,
                }
            )


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _is_top(heading: str) -> bool:
    return bool(_TOP_SECTION.match(_norm_heading(heading)))


def _is_plain_heading(line: str) -> bool:
    if line.startswith("#"):
        return True
    if line.endswith((".", "?", "!")):
        return False
    heading, _ = _heading_text(line)
    norm = _norm_heading(heading)
    if _is_top(heading) or _is_skip_title(heading):
        return True
    if _words(heading) <= 8 and any(key in norm for key in _HEADING_HINTS):
        return True
    letters = [ch for ch in heading if ch.isalpha()]
    return bool(letters) and heading.upper() == heading and _words(heading) <= 6


def _heading_text(line: str) -> tuple[str, bool]:
    match = re.match(r"^(#+)\s+(.*)$", line)
    if match:
        return match.group(2).strip(), len(match.group(1)) == 1
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", line).strip(), False


def _first_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
        return ""
    return ""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def _element_text(el: ET.Element) -> str:
    chunks: list[str] = []

    def rec(node: ET.Element, *, root: bool) -> None:
        if not root and _local(node.tag) in _SKIP_INLINE:
            if node.tail:
                chunks.append(node.tail)
            return
        if node.text:
            chunks.append(node.text)
        for child in list(node):
            rec(child, root=False)
        if node.tail and not root:
            chunks.append(node.tail)

    rec(el, root=True)
    return "".join(chunks)


def _walk_sec(sec: ET.Element, path: list[str], parent_zone: str, blocks: list[Block], *, abstract: bool) -> None:
    if _local(sec.tag) == "trans-abstract":
        return
    title = ""
    for child in list(sec):
        if _local(child.tag) == "title":
            title = _clean(_element_text(child))
            break
    sec_type = (sec.get("sec-type") or "").lower()
    if sec_type in _SKIP_SEC_TYPE or (title and _is_skip_title(title)):
        return
    zone = zone_for(title, parent_zone) if title else parent_zone
    if abstract and not title and parent_zone == "abstract":
        zone = "abstract"
    if zone == "skip":
        return
    here = path + ([title] if title else [])
    section = " → ".join(here) if here else ("Аннотация" if abstract else "Текст")
    proto = protocol_section(title, zone) if title else False
    for child in list(sec):
        name = _local(child.tag)
        if name in {"title", "label"}:
            continue
        if name == "sec":
            _walk_sec(child, here, zone, blocks, abstract=False)
            continue
        if name in {"fig", "table-wrap", "table", "graphic", "caption", "fig-group", "glossary"}:
            continue
        if name == "p":
            paragraph = _clean(_element_text(child))
            if paragraph and not paragraph.lower().startswith("keywords"):
                blocks.append(Block(section=section, zone=zone, protocol_section=proto, text=paragraph))
            continue
        if name == "list":
            for item in list(child):
                if _local(item.tag) != "list-item":
                    continue
                paragraph = _clean(_element_text(item))
                if paragraph:
                    blocks.append(Block(section=section, zone=zone, protocol_section=proto, text=paragraph))

