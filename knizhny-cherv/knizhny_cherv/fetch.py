"""Скачать открытые статьи на отдельную полку и отметить результат в библиографии."""

from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from knizhny_cherv.export import (
    load_availability,
    read_csv,
    save_availability,
    write_bibliography,
)
from knizhny_cherv.fulltext import acquire, public_source_url
from knizhny_cherv.models import Paper
from knizhny_cherv.presets import Preset
from knizhny_cherv.shelf import (
    assert_library_is_separate,
    ensure_layout,
    place_article,
    write_catalog,
)


def run_fetch(
    out_dir: Path,
    library: Path,
    presets: list[Preset],
    *,
    opener=None,
    pause_s: float = 0.25,
    generated_on: str,
    library_url: str = "",
    start: Path | None = None,
) -> dict[str, dict]:
    assert_library_is_separate(library, start)
    unique_path = out_dir / "unique.csv"
    if not unique_path.exists():
        raise ValueError(f"нет {unique_path}: сначала соберите библиографию командой presets")
    papers = read_csv(unique_path)
    ensure_layout(library, presets)
    known = {preset.id for preset in presets}
    previous = load_availability(out_dir / "files.json") or {}
    items = fetch_papers(
        papers,
        library,
        known_topics=known,
        previous=previous,
        opener=opener,
        pause_s=pause_s,
    )
    save_availability(out_dir / "files.json", items, library_url=library_url)
    grouped: list[tuple[Preset, list[Paper]]] = []
    limit = 1
    for preset in presets:
        topic_csv = out_dir / f"{preset.id}.csv"
        topic_papers = read_csv(topic_csv) if topic_csv.exists() else []
        grouped.append((preset, topic_papers))
        limit = max(limit, len(topic_papers))
    write_bibliography(
        out_dir / "bibliography.md",
        grouped,
        generated_on=generated_on,
        limit=limit,
        availability=items,
    )
    write_catalog(library, presets, papers, items)
    return items


def fetch_papers(
    papers: list[Paper],
    library: Path,
    *,
    known_topics: set[str],
    previous: dict[str, dict] | None = None,
    opener=None,
    pause_s: float = 0.0,
) -> dict[str, dict]:
    fetch = opener or urllib.request.urlopen
    items: dict[str, dict] = {}
    stored = previous or {}
    for index, paper in enumerate(papers):
        key = paper.key()
        prior = stored.get(key) or {}
        if prior.get("status") == "saved" and prior.get("path"):
            existing = library / str(prior["path"])
            if existing.is_file():
                items[key] = dict(prior)
                continue
        if index and pause_s:
            time.sleep(pause_s)
        result = acquire(paper, fetch)
        record = {
            "status": result.status,
            "format": result.format,
            "path": "",
            "reason": result.reason,
            "source_url": public_source_url(result.source_url),
        }
        if result.status == "saved" and result.data:
            record["path"] = place_article(library, paper, result.data, result.format, known_topics)
        items[key] = record
    return items
