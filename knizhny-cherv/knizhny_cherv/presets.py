"""Готовые запросы обзора in vitro maturation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

QUERIES_PATH = Path(__file__).resolve().parent.parent / "queries" / "ivm.json"


@dataclass(frozen=True)
class Preset:
    id: str
    title: str
    question: str
    query: str


def load_presets(path: Path | None = None) -> list[Preset]:
    source = path or QUERIES_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    presets: list[Preset] = []
    for item in raw:
        presets.append(
            Preset(
                id=str(item["id"]),
                title=str(item["title"]),
                question=str(item["question"]),
                query=str(item["query"]),
            )
        )
    if not presets:
        raise ValueError(f"в {source} нет запросов")
    return presets
