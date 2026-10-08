"""Прозектор: разбор статьи в таблицы дословных цитат.

Цитата — предложение из текста статьи без пересказа и без перевода.
Выход Прозектора — файл .docx. Столбец «Ссылки» — пункты списка литературы самой статьи.
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
    "protocol": "Нумерованный список дословных шагов. Перед списком — как это делают.",
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
class Reference:
    """Пункт списка литературы разбираемой статьи."""

    label: str
    text: str
    href: str


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
    authors: str = ""
    year: str = ""
    doi: str = ""
    references: tuple[Reference, ...] = ()

    @property
    def completeness(self) -> str:
        zones = {block.zone for block in self.blocks}
        if "methods" in zones and zones & {"results", "discussion"}:
            return "полный текст"
        return "фрагмент или аннотация"


@dataclass(frozen=True)
class Quote:
    bucket: str
    section: str
    text: str
    plain: str
    refs: tuple[Reference, ...] = ()


@dataclass
class Prozektor:
    document: Document
    quotes: list[Quote]
    sentences_seen: int = 0

    def by_bucket(self, bucket: str) -> list[Quote]:
        return [quote for quote in self.quotes if quote.bucket == bucket]


def normalize_superscript_citations(text: str) -> str:
    """Надстрочные номера Cell превратить в [1–4], не трогая десятичные дроби и DOI.

    «burdens.1–4 Despite» становится «burdens [1–4]. Despite».
    «lagged,5,6 hindering» становится «lagged [5,6] hindering».
    """
    nums = r"\d{1,3}(?:[\u2013\-]\d{1,3})?(?:,\d{1,3}(?:[\u2013\-]\d{1,3})?)*"

    def citation(raw: str) -> str | None:
        parts = re.split(r"[,|\u2013\-]", raw)
        if any(not part or (len(part) > 1 and part.startswith("0")) for part in parts):
            return None
        return raw

    def sentence_end(match: re.Match[str]) -> str:
        raw = citation(match.group(2))
        if raw is None:
            return match.group(0)
        return f" [{raw}]{match.group(1)} "

    def inline(match: re.Match[str]) -> str:
        raw = citation(match.group(1))
        if raw is None:
            return match.group(0)
        return f" [{raw}]"

    text = re.sub(
        rf"(?<=[A-Za-z])([.!?])({nums})(?!\d)(?=\s+[A-ZА-ЯЁ]|$)",
        sentence_end,
        text,
    )
    text = re.sub(
        rf"(?<=[A-Za-z]),({nums})(?!\d)(?=\s)",
        inline,
        text,
    )
    text = re.sub(
        rf"(?<=[a-z])\.({nums})(?!\d)(?=\s+[a-z])",
        inline,
        text,
    )
    return " ".join(text.split())


def split_sentences(text: str) -> list[str]:
    """Разбить абзац на предложения, не режа десятичные дроби и Fig. / et al."""
    raw = normalize_superscript_citations(text)
    raw = " ".join(raw.replace("\xa0", " ").split())
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


def citation_labels(sentence: str) -> list[str]:
    """Номера в квадратных скобках: [2], [3, 4], [9–11]."""
    labels: list[str] = []
    for match in _BRACKET_CIT.finditer(sentence):
        inner = match.group().strip()[1:-1]
        for part in re.split(r"\s*,\s*", inner):
            span = re.match(r"(\d+)\s*[\u2013\-]\s*(\d+)$", part.strip())
            if span:
                start, end = int(span.group(1)), int(span.group(2))
                if 0 < end - start <= 20:
                    labels.extend(str(number) for number in range(start, end + 1))
                else:
                    labels.extend((span.group(1), span.group(2)))
                continue
            number = re.search(r"\d+", part)
            if number:
                labels.append(number.group())
    unique: list[str] = []
    for label in labels:
        if label not in unique:
            unique.append(label)
    return unique


def resolve_references(sentence: str, references: tuple[Reference, ...]) -> tuple[Reference, ...]:
    """Найти в списке литературы статьи те пункты, на которые ссылается предложение."""
    if not references:
        return ()
    by_label = {ref.label: ref for ref in references}
    found: list[Reference] = []
    seen: set[str] = set()
    for label in citation_labels(sentence):
        ref = by_label.get(label)
        if ref and ref.label not in seen:
            found.append(ref)
            seen.add(ref.label)
    for match in _AUTHOR_YEAR.finditer(sentence):
        chunk = match.group()
        years = re.findall(r"\d{4}", chunk)
        surnames = [name for name in re.findall(r"[A-Z][A-Za-z'’\-]+", chunk) if name.lower() != "et"]
        for ref in references:
            if ref.label in seen:
                continue
            haystack = ref.text.lower()
            if years and surnames and any(year in ref.text for year in years) and any(name.lower() in haystack for name in surnames):
                found.append(ref)
                seen.add(ref.label)
    return tuple(found)


def format_reference(ref: Reference) -> str:
    text = f"{ref.label}. {ref.text}".strip()
    if ref.href and ref.href not in text:
        text = f"{text} {ref.href}"
    return text


def format_references(refs: tuple[Reference, ...]) -> str:
    if not refs:
        return "—"
    return "; ".join(format_reference(ref) for ref in refs)


_HOW_TO: tuple[tuple[str, str, str], ...] = (
    (
        "in vivo oocyte maturation",
        "созревание in vivo",
        "Расширенные клетки кумулюса рвут щелевые контакты комплекса, перенос cAMP и cGMP прекращается, мейоз возобновляется через MPF.",
    ),
    (
        "in vitro oocyte maturation",
        "обычный IVM",
        "Незрелые комплексы культивируют от профазы I до метафазы II и гонадотропины не вводят.",
    ),
    (
        "fsh priming",
        "FSH priming",
        "Несколько дней до пункции вводят ФСГ. Фолликулы 2–6 мм несут рецепторы ФСГ, мейоз in vivo не запускают и забирают незрелые компактные комплексы. В цитируемых работах это 600 МЕ в течение 5 дней со 2-го дня цикла или 150 МЕ в течение 2–3 дней со 2–3-го дня.",
    ),
    (
        "hcgpriming",
        "hCG priming",
        "Перед пункцией вводят ХГЧ, чтобы начать созревание in vivo и повысить долю ооцитов, которые дозреют in vitro. У женщин со СПКЯ доля зрелых к 48 часам была выше; без СПКЯ один только ХГЧ исход не улучшал.",
    ),
    (
        "hcg priming",
        "hCG priming",
        "Перед пункцией вводят ХГЧ, чтобы начать созревание in vivo и повысить долю ооцитов, которые дозреют in vitro.",
    ),
    (
        "timing of oocyte retrieval",
        "выбор срока пункции",
        "Одни ждут лидирующий фолликул 10 мм, другие считают это поводом отменить цикл. Son и соавторы забирают ооциты, пока доминантный фолликул не больше 14 мм, а интервал после ХГЧ удлиняют с 35 до 38 часов.",
    ),
    (
        "oocyte retrieval",
        "пункцию",
        "Фолликулы мелкие, примерно 2–12 мм, комплекс сидит на стенке плотнее, чем в ЭКО. Игла обычно 16–21 gauge, в части клиник система из двух игл.",
    ),
    (
        "culture medium",
        "культуру незрелых ооцитов",
        "В pre-IVM примерно на 2 часа удерживают ооцит от спонтанного созревания аналогами cAMP, ингибиторами киназ или ФДЭ. В схеме с CNP герминальный пузырёк держат 24 часа, щелевые контакты сохраняются дольше.",
    ),
    (
        "culture time",
        "оценку зрелости и осеменение",
        "В циклах с ХГЧ зрелые in vivo ищут в день пункции и на следующий день. В ранних работах зрелость смотрели через 48 или 56 часов культуры.",
    ),
    (
        "embryo transfer",
        "культуру эмбрионов, перенос и криоконсервацию",
        "После оплодотворения эмбрионы ведут так же, как в обычном ЭКО. Витрифицируют и дробящиеся эмбрионы, и бластоцисты.",
    ),
    (
        "endometrial preparation",
        "подготовку эндометрия",
        "Если к 6–10 дню эндометрий тоньше 6 мм, сравнивали низкие дозы чМГ и микронизированный эстроген 6–12 мг/сут. Эстроген с середины фолликулярной фазы давал лучшее созревание, чем ранний старт.",
    ),
    (
        "freeze all",
        "freeze-all",
        "После IVM эмбрионы витрифицируют и переносят в криоцикле. В статье это серия пациенток со СПКЯ и перенос на стадии дробления.",
    ),
    (
        "ivm for pcos",
        "IVM при СПКЯ",
        "В цитируемом РКИ делают один цикл без гонадотропинов и переносят одну витрифицированную бластоцисту.",
    ),
    (
        "fertility preservation",
        "сохранение фертильности",
        "Незрелые ооциты забирают в любой фазе цикла. Для хотя бы 10 ооцитов в статье называют AFC больше 20 и АМГ 3,7 нг/мл. Культура 48 часов, затем витрификация.",
    ),
    (
        "natural cycle",
        "natural cycle IVF/IVM",
        "Вводят 10 000 МЕ ХГЧ, когда доминантный фолликул больше 12 мм, и доводят также ооциты из меньших фолликулов. Сравнивают фолликулы до 10 мм и больше 11 мм.",
    ),
    (
        "poor responder",
        "IVM у бедных ответчиц",
        "Если зрелых MII меньше пяти и есть хотя бы один незрелый, его оставляют в культуре до спонтанного созревания и делают ИКСИ.",
    ),
    (
        "long term safety",
        "витрификацию ооцитов после IVM",
        "Cohen и соавторы описывают пять живорождений после витрификации и отогрева ооцитов, созревших in vitro, у женщин со СПКЯ.",
    ),
    (
        "key challenges",
        "поиск незрелых комплексов",
        "В аспирате комплексы ищут дольше: кумулюс не расширен и по цвету похож на гранулёзу. Среду каждая лаборатория готовит сама.",
    ),
    (
        "ivm protocol",
        "IVM в этой работе",
        "Пунктируют иглой 19 gauge при 80 мм рт. ст. Незрелые комплексы культивируют в среде с 0,075 МЕ/мл ФСГ 30 часов и оплодотворяют ИКСИ.",
    ),
)


def how_to(section: str) -> tuple[str, str]:
    """Заголовок и описание перед нумерованным списком шагов."""
    name = section.split("→")[-1].strip()
    key = _norm_heading(name)
    for needle, title, body in _HOW_TO:
        if needle in key:
            return f"Как сделать {title}", body
    return f"Как сделать {name}", "Ниже дословные шаги и схемы из статьи, по порядку."


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
            refs = resolve_references(sentence, document.references)
            for bucket in BUCKETS:
                if bucket not in chosen:
                    continue
                key = (bucket, sentence)
                if key in seen:
                    continue
                seen.add(key)
                quotes.append(Quote(bucket=bucket, section=block.section, text=sentence, plain=plain, refs=refs))
    return Prozektor(document=document, quotes=quotes, sentences_seen=sentences_seen)


_BIBLIO_HEADINGS = {
    "references",
    "bibliography",
    "литература",
    "список литературы",
    "библиография",
}

_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_URL = re.compile(r"https?://\S+")


def _is_bibliography(heading: str) -> bool:
    return _norm_heading(heading) in _BIBLIO_HEADINGS


def _href_from_text(text: str) -> str:
    url = _URL.search(text)
    if url:
        return url.group().rstrip(").,;")
    doi = _DOI.search(text)
    if doi:
        return "https://doi.org/" + doi.group().rstrip(").,;")
    return ""


def _references_from_lines(lines: list[str]) -> tuple[Reference, ...]:
    """Пункты 1. 2. 3. по порядку. «Part 1.» и номер страницы новым пунктом не становятся."""
    text = " ".join(" ".join(line.split()) for line in lines if line.strip())
    refs: list[Reference] = []
    expected = 1
    starts: list[re.Match[str]] = []
    for match in re.finditer(r"(?:(?<=\s)|^)(\d{1,3})\.\s+", text):
        if int(match.group(1)) != expected:
            continue
        before = text[max(0, match.start() - 6):match.start()].lower()
        if before.endswith("part ") or before.endswith("part"):
            continue
        starts.append(match)
        expected += 1
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[match.end():end].strip()
        refs.append(Reference(label=match.group(1), text=body, href=_href_from_text(body)))
    return tuple(refs)


def _references_from_jats(article: ET.Element) -> tuple[Reference, ...]:
    refs: list[Reference] = []
    for el in article.iter():
        if _local(el.tag) != "ref":
            continue
        label = ""
        citation = None
        for child in el.iter():
            name = _local(child.tag)
            if name == "label" and not label:
                label = _clean(_element_text(child))
            elif name in {"mixed-citation", "element-citation", "citation"} and citation is None:
                citation = child
        label = label.rstrip(".")
        if not label:
            match = re.search(r"(\d+)$", el.get("id") or "")
            label = match.group(1) if match else str(len(refs) + 1)
        source = citation if citation is not None else el
        text = _spaced_text(source)
        text = re.sub(rf"^{re.escape(label)}[.\s]+", "", text).strip()
        refs.append(Reference(label=label, text=text, href=_href_from_element(source) or _href_from_text(text)))
    return tuple(refs)


def _spaced_text(el: ET.Element) -> str:
    parts: list[str] = []

    def rec(node: ET.Element) -> None:
        if node.text and node.text.strip():
            parts.append(node.text.strip())
        for child in list(node):
            rec(child)
            if child.tail and child.tail.strip():
                parts.append(child.tail.strip())

    rec(el)
    return _clean(" ".join(parts))


def _href_from_element(el: ET.Element) -> str:
    xlink = "{http://www.w3.org/1999/xlink}href"
    doi = ""
    pmid = ""
    for child in el.iter():
        name = _local(child.tag)
        if name not in {"ext-link", "pub-id", "article-id"}:
            continue
        kind = (child.get("ext-link-type") or child.get("pub-id-type") or "").lower()
        raw = (child.get(xlink) or child.get("href") or child.text or "").strip()
        if kind == "doi" or raw.startswith("10."):
            doi = raw.removeprefix("https://doi.org/").removeprefix("http://dx.doi.org/")
        elif kind == "pmid" and raw.isdigit():
            pmid = raw
    if doi:
        return "https://doi.org/" + doi.rstrip(").,;")
    if pmid:
        return "https://pubmed.ncbi.nlm.nih.gov/" + pmid
    return ""


def parse_article(text: str, *, source: str = "") -> Document:
    stripped = text.lstrip()
    if stripped.startswith("<"):
        return parse_jats(text, source=source)
    return parse_plain(text, source=source)


_META_LINE = re.compile(r"(?i)^(authors|авторы|year|год|doi|source|источник)\s*:\s*(.+)$")


def parse_plain(text: str, *, source: str = "") -> Document:
    title = ""
    authors = ""
    year = ""
    doi = ""
    source_meta = ""
    blocks: list[Block] = []
    bibliography: list[str] = []
    top = ""
    sub = ""
    zone = "other"
    proto = False
    buffer: list[str] = []

    def section_path() -> str:
        parts = [part for part in (top, sub) if part]
        return " → ".join(parts) if parts else "Текст"

    def flush() -> None:
        if not buffer:
            return
        paragraph = " ".join(" ".join(buffer).split())
        buffer.clear()
        if not paragraph:
            return
        if zone == "skip":
            if _is_bibliography(top):
                bibliography.append(paragraph)
            return
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
        meta = _META_LINE.match(line)
        if meta and not blocks and not buffer:
            key = meta.group(1).lower()
            value = meta.group(2).strip()
            if key in {"authors", "авторы"}:
                authors = value
            elif key in {"year", "год"}:
                year = value
            elif key == "doi":
                doi = value.removeprefix("https://doi.org/").removeprefix("http://dx.doi.org/")
            elif key in {"source", "источник"}:
                source_meta = value
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
    return Document(
        title=title or "Без названия",
        language=language_of(full),
        blocks=blocks,
        full_text=full,
        source=source_meta or source,
        authors=authors,
        year=year,
        doi=doi,
        references=_references_from_lines(bibliography),
    )


def _article_meta(article: ET.Element) -> tuple[str, str, str]:
    names: list[str] = []
    for el in article.iter():
        if _local(el.tag) != "contrib":
            continue
        if (el.get("contrib-type") or "author") != "author":
            continue
        surname = ""
        given = ""
        collab = ""
        for child in el.iter():
            local = _local(child.tag)
            if local == "surname" and not surname:
                surname = _clean(_element_text(child))
            elif local == "given-names" and not given:
                given = _clean(_element_text(child))
            elif local == "collab" and not collab:
                collab = _clean(_element_text(child))
        if surname:
            names.append(f"{surname} {given}".strip())
        elif collab:
            names.append(collab)
        if len(names) >= 20:
            break
    year = ""
    for el in article.iter():
        if _local(el.tag) != "pub-date":
            continue
        for child in list(el):
            if _local(child.tag) == "year" and (child.text or "").strip().isdigit():
                year = child.text.strip()
                break
        if year and (el.get("pub-type") or "") in {"epub", "ppub", "collection"}:
            break
    doi = ""
    for el in article.iter():
        if _local(el.tag) != "article-id":
            continue
        if (el.get("pub-id-type") or "").lower() == "doi" and (el.text or "").strip():
            doi = el.text.strip()
            break
    return ", ".join(names), year, doi


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
    authors, year, doi = _article_meta(article)
    references = _references_from_jats(article)
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
        authors=authors,
        year=year,
        doi=doi,
        references=references,
    )


def render_markdown(prozektor: Prozektor) -> str:
    document = prozektor.document
    lines = [
        f"# Прозектор: {document.title}",
        "",
        "Цитаты дословные и на языке статьи. Английский не переводится.",
        "В столбце «Ссылки» стоят пункты списка литературы этой статьи, на которые опирается фраза, вместе с адресом, если он в статье есть.",
        "",
        "Благодарности, финансирование, декларации и подписи к рисункам Прозектор не включает.",
        "",
        *( [f"- Авторы: {document.authors}"] if document.authors else [] ),
        *( [f"- Год: {document.year}"] if document.year else [] ),
        *( [f"- DOI: {document.doi}"] if document.doi else [] ),
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
        if bucket == "protocol":
            lines.extend(_protocol_lines(rows))
            continue
        lines.append("| # | Раздел | Цитата | Ссылки |")
        lines.append("|---:|---|---|---|")
        for index, quote in enumerate(rows, start=1):
            lines.append(
                "| "
                + " | ".join(
                    (
                        str(index),
                        _cell(quote.section),
                        _cell(quote.text),
                        _cell(format_references(quote.refs)),
                    )
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _protocol_lines(rows: list[Quote]) -> list[str]:
    lines: list[str] = []
    groups: list[tuple[str, list[Quote]]] = []
    for quote in rows:
        if not groups or groups[-1][0] != quote.section:
            groups.append((quote.section, []))
        groups[-1][1].append(quote)
    for section, quotes in groups:
        title, body = how_to(section)
        lines.append(f"### {title}")
        lines.append("")
        lines.append(body)
        lines.append("")
        for index, quote in enumerate(quotes, start=1):
            lines.append(f"{index}. {quote.text}")
            lines.append("")
            lines.append(f"   Ссылки: {format_references(quote.refs)}")
            lines.append("")
    return lines


def write_markdown(path, prozektor: Prozektor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(prozektor), encoding="utf-8")


def write_quotes_csv(path, prozektor: Prozektor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("bucket", "section", "quote", "references"),
        )
        writer.writeheader()
        for quote in prozektor.quotes:
            writer.writerow(
                {
                    "bucket": quote.bucket,
                    "section": quote.section,
                    "quote": quote.text,
                    "references": format_references(quote.refs),
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

