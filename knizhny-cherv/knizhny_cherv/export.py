"""Выгрузка найденных статей в CSV и Markdown."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from knizhny_cherv.models import Paper
from knizhny_cherv.presets import Preset

CSV_FIELDS = [
    "query_id",
    "year",
    "title",
    "authors",
    "journal",
    "doi",
    "pmid",
    "pmcid",
    "cited_by",
    "open_access",
    "pub_types",
    "url",
    "abstract",
]


def write_csv(path: Path, papers: list[Paper]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for paper in papers:
            writer.writerow(
                {
                    "query_id": paper.query_id,
                    "year": paper.year,
                    "title": paper.title,
                    "authors": paper.authors,
                    "journal": paper.journal,
                    "doi": paper.doi,
                    "pmid": paper.pmid,
                    "pmcid": paper.pmcid,
                    "cited_by": paper.cited_by,
                    "open_access": "yes" if paper.open_access else "no",
                    "pub_types": paper.pub_types,
                    "url": paper.url,
                    "abstract": paper.abstract,
                }
            )


def write_bibliography(
    path: Path,
    grouped: list[tuple[Preset, list[Paper]]],
    *,
    generated_on: str,
    limit: int,
    availability: dict[str, dict] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Библиография: in vitro maturation",
        "",
        f"Собрано проектом «Книжный червь» из Europe PMC, {generated_on}.",
        f"До {limit} записей на каждый вопрос, сортировка источника — релевантность.",
        "Аннотации сохранены в соседних CSV и пригодны для скрининга.",
        "",
    ]
    if availability is not None:
        lines.extend(
            [
                "Полные тексты (pdf, docx, djvu) лежат в отдельном репозитории статей и разложены по темам обзора.",
                "Если открытую копию скачать нельзя, у записи написано «скачивание невозможно».",
                "",
            ]
        )
    for preset, papers in grouped:
        lines.append(f"## {preset.title}")
        lines.append("")
        lines.append(preset.question)
        lines.append("")
        lines.append(f"Запрос: `{preset.query}`")
        lines.append("")
        lines.append(f"Найдено в этой выгрузке: {len(papers)}.")
        lines.append("")
        if not papers:
            lines.append("Записей нет.")
            lines.append("")
            continue
        for index, paper in enumerate(papers, start=1):
            lines.append(f"### {index}. {paper.title}")
            lines.append("")
            lines.append(f"- Год: {paper.year or '—'}")
            lines.append(f"- Авторы: {paper.authors or '—'}")
            lines.append(f"- Журнал: {paper.journal or '—'}")
            lines.append(f"- DOI: {paper.doi or '—'}")
            lines.append(f"- PMID: {paper.pmid or '—'}")
            if paper.pmcid:
                lines.append(f"- PMCID: {paper.pmcid}")
            lines.append(f"- Цитирования: {paper.cited_by}")
            lines.append(f"- Открытый доступ: {'да' if paper.open_access else 'нет'}")
            if paper.pub_types:
                lines.append(f"- Типы: {paper.pub_types}")
            if paper.url:
                lines.append(f"- Ссылка: {paper.url}")
            note = file_note(paper, availability)
            if note:
                lines.append(note)
            lines.append("")
            if paper.abstract:
                lines.append(paper.abstract)
                lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def file_note(paper: Paper, availability: dict[str, dict] | None) -> str:
    """Строка списка литературы про файл или про невозможность скачать его."""
    if availability is None:
        return ""
    record = availability.get(paper.key())
    if not record:
        return "- Файл: ещё не проверялся"
    if record.get("status") == "saved" and record.get("path"):
        fmt = str(record.get("format") or "файл")
        return f"- Файл: {fmt}, репозиторий статей, `{record['path']}`"
    reason = str(record.get("reason") or "нет открытого полного текста")
    return f"- Файл: скачивание невозможно ({reason})"


def read_csv(path: Path) -> list[Paper]:
    with path.open(encoding="utf-8", newline="") as handle:
        papers: list[Paper] = []
        for row in csv.DictReader(handle):
            try:
                cited_by = int(row.get("cited_by") or 0)
            except ValueError:
                cited_by = 0
            papers.append(
                Paper(
                    query_id=row.get("query_id") or "",
                    pmid=row.get("pmid") or "",
                    pmcid=row.get("pmcid") or "",
                    doi=row.get("doi") or "",
                    year=row.get("year") or "",
                    title=row.get("title") or "",
                    authors=row.get("authors") or "",
                    journal=row.get("journal") or "",
                    cited_by=cited_by,
                    open_access=(row.get("open_access") or "") == "yes",
                    pub_types=row.get("pub_types") or "",
                    abstract=row.get("abstract") or "",
                    url=row.get("url") or "",
                )
            )
    return papers


def load_availability(path: Path) -> dict[str, dict] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    items = payload.get("items")
    if not isinstance(items, dict):
        return {}
    return {str(key): value for key, value in items.items() if isinstance(value, dict)}


def save_availability(path: Path, items: dict[str, dict], *, library_url: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not library_url:
        previous = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(previous, dict):
            library_url = str(previous.get("library_url") or "")
    payload = {"library_url": library_url, "items": items}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dedupe(papers: list[Paper]) -> list[Paper]:
    """Оставить первое вхождение каждой статьи, склеив id запросов."""
    order: list[str] = []
    by_key: dict[str, Paper] = {}
    queries: dict[str, list[str]] = {}
    for paper in papers:
        key = paper.key()
        if key not in by_key:
            by_key[key] = paper
            order.append(key)
            queries[key] = [paper.query_id] if paper.query_id else []
            continue
        if paper.query_id and paper.query_id not in queries[key]:
            queries[key].append(paper.query_id)
    unique: list[Paper] = []
    for key in order:
        paper = by_key[key]
        joined = ";".join(queries[key])
        if joined != paper.query_id:
            paper = Paper(
                query_id=joined,
                pmid=paper.pmid,
                pmcid=paper.pmcid,
                doi=paper.doi,
                year=paper.year,
                title=paper.title,
                authors=paper.authors,
                journal=paper.journal,
                cited_by=paper.cited_by,
                open_access=paper.open_access,
                pub_types=paper.pub_types,
                abstract=paper.abstract,
                url=paper.url,
            )
        unique.append(paper)
    return unique
