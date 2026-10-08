"""Каталог статей вне репозитория обзора: папка на каждую тему."""

from __future__ import annotations

import json
import re
from pathlib import Path

from knizhny_cherv.models import Paper
from knizhny_cherv.presets import Preset

_SLUG = re.compile(r"[^\w.\-]+", re.UNICODE)


def git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def assert_library_is_separate(library: Path, start: Path | None = None) -> None:
    """Полные тексты не должны попасть в репозиторий обзора."""
    library = library.resolve()
    root = git_root(start or Path.cwd())
    if root is not None and (library == root or root in library.parents):
        raise ValueError("каталог статей должен лежать вне репозитория обзора")


def topics_of(paper: Paper) -> list[str]:
    return [part.strip() for part in paper.query_id.split(";") if part.strip()]


def article_basename(paper: Paper, ext: str) -> str:
    author = "anon"
    if paper.authors:
        first = paper.authors.split(",")[0].strip()
        if first:
            author = first.split()[0]
    if paper.pmcid:
        ident = paper.pmcid
    elif paper.pmid:
        ident = "PMID" + paper.pmid
    elif paper.doi:
        ident = paper.doi.replace("/", "_")
    else:
        ident = paper.key()
    year = _slug(paper.year, 4) or "nd"
    return f"{year}_{_slug(author, 24) or 'anon'}_{_slug(ident, 60)}.{ext}"


def ensure_layout(library: Path, presets: list[Preset]) -> None:
    library.mkdir(parents=True, exist_ok=True)
    readme = library / "README.md"
    if not readme.exists():
        lines = [
            "# Статьи по in vitro maturation",
            "",
            "Отдельный репозиторий полных текстов. Обзор и список литературы живут в",
            "[in-vitro-maturation](https://github.com/Tartartal/in-vitro-maturation), без этих файлов.",
            "",
            "Принимаются только `.pdf`, `.docx` и `.djvu`. Папки совпадают с темами обзора.",
            "Статья, которая отвечает сразу на несколько вопросов, хранится в папке первой темы",
            "и перечислена в `CATALOG.md` у каждой из них.",
            "",
            "Сюда попадают открытые копии. Если файл скачать нельзя, это записано в списке",
            "литературы обзора, а не пустым файлом здесь.",
            "",
            "У каждого файла остаётся лицензия самой статьи. Этот репозиторий — личная полка,",
            "а не передача прав на тексты.",
            "",
            "## Темы",
            "",
        ]
        for preset in presets:
            lines.append(f"- `{preset.id}` — {preset.title}. {preset.question}")
        lines.append("")
        readme.write_text("\n".join(lines), encoding="utf-8")
    for preset in presets:
        folder = library / preset.id
        folder.mkdir(exist_ok=True)
        note = folder / "README.md"
        if not note.exists():
            note.write_text(f"# {preset.title}\n\n{preset.question}\n", encoding="utf-8")
    gitignore = library / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\n*.tmp\n.DS_Store\n", encoding="utf-8")


def place_article(library: Path, paper: Paper, data: bytes, ext: str, known_topics: set[str]) -> str:
    """Положить файл в папку первой темы и вернуть путь относительно полки."""
    topics = topics_of(paper) or ["other"]
    primary = topics[0] if topics[0] in known_topics else "other"
    folder = library / primary
    folder.mkdir(parents=True, exist_ok=True)
    name = article_basename(paper, ext)
    path = folder / name
    if path.exists() and path.read_bytes() != data:
        stem = path.stem
        suffix = path.suffix
        number = 2
        while path.exists() and path.read_bytes() != data:
            path = folder / f"{stem}-{number}{suffix}"
            number += 1
    path.write_bytes(data)
    return path.relative_to(library).as_posix()


def write_catalog(
    library: Path,
    presets: list[Preset],
    papers: list[Paper],
    items: dict[str, dict],
) -> None:
    by_key = {paper.key(): paper for paper in papers}
    saved = [(key, record) for key, record in items.items() if record.get("status") == "saved" and record.get("path")]
    lines = [
        "# Каталог",
        "",
        "Файлы разложены по темам обзора. Если статья относится к нескольким темам,",
        "файл лежит в первой из них, а в остальных разделах на него дана ссылка.",
        "",
        "Статьи без файла в этот каталог не входят: в списке литературы обзора у них",
        "стоит пометка «скачивание невозможно».",
        "",
    ]
    used: set[str] = set()
    for preset in presets:
        lines.append(f"## {preset.title}")
        lines.append("")
        section = []
        for key, record in saved:
            paper = by_key.get(key)
            topics = topics_of(paper) if paper else [record.get("path", "").split("/", 1)[0]]
            if preset.id not in topics and not str(record.get("path", "")).startswith(preset.id + "/"):
                continue
            used.add(key)
            section.append(_catalog_line(paper, record, preset.id))
        if not section:
            lines.append("Файлов пока нет.")
            lines.append("")
            continue
        lines.extend(section)
        lines.append("")
    leftovers = [pair for pair in saved if pair[0] not in used]
    if leftovers:
        lines.append("## Прочее")
        lines.append("")
        for key, record in leftovers:
            lines.append(_catalog_line(by_key.get(key), record, ""))
        lines.append("")
    (library / "CATALOG.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    manifest = []
    for key, record in saved:
        paper = by_key.get(key)
        manifest.append(
            {
                "key": key,
                "path": record.get("path") or "",
                "format": record.get("format") or "",
                "title": paper.title if paper else "",
                "year": paper.year if paper else "",
                "authors": paper.authors if paper else "",
                "topics": topics_of(paper) if paper else [],
                "source_url": record.get("source_url") or "",
            }
        )
    (library / "manifest.json").write_text(
        json.dumps({"items": manifest}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _catalog_line(paper: Paper | None, record: dict, section_id: str) -> str:
    path = str(record.get("path") or "")
    folder = path.split("/", 1)[0]
    if paper:
        text = f"- {paper.year or '—'}. {paper.authors or '—'}. {paper.title} — `{path}`"
    else:
        text = f"- `{path}`"
    if section_id and folder and folder != section_id:
        text += f" (файл в папке `{folder}`)"
    return text


def _slug(text: str, limit: int) -> str:
    cleaned = _SLUG.sub("_", text).strip("._")
    return cleaned[:limit]
