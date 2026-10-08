"""Командная строка Книжного червя."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from knizhny_cherv.europepmc import SearchError, search
from knizhny_cherv.export import dedupe, load_availability, with_added, write_bibliography, write_csv
from knizhny_cherv.fetch import run_fetch
from knizhny_cherv.presets import load_presets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knizhny-cherv",
        description="Поиск литературы по in vitro maturation в Europe PMC.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search_parser = sub.add_parser("search", help="один произвольный запрос")
    search_parser.add_argument("query", help="синтаксис Europe PMC")
    search_parser.add_argument("--limit", type=int, default=25)
    search_parser.add_argument("--sort", choices=("relevance", "cited", "date"), default="relevance")
    search_parser.add_argument("--query-id", default="custom")
    search_parser.add_argument("--out", type=Path, required=True, help="CSV с результатами")

    presets_parser = sub.add_parser("presets", help="пять вопросов обзора IVM")
    presets_parser.add_argument("--limit", type=int, default=20)
    presets_parser.add_argument("--sort", choices=("relevance", "cited", "date"), default="relevance")
    presets_parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("literature/ivm"),
        help="каталог CSV и bibliography.md",
    )
    presets_parser.add_argument("--queries", type=Path, default=None, help="JSON с вопросами вместо встроенного")

    list_parser = sub.add_parser("list-presets", help="показать встроенные запросы")
    list_parser.add_argument("--queries", type=Path, default=None)

    fetch_parser = sub.add_parser("fetch", help="скачать открытые pdf, docx и djvu в отдельный репозиторий")
    fetch_parser.add_argument("--out-dir", type=Path, default=Path("literature/ivm"))
    fetch_parser.add_argument("--library", type=Path, required=True, help="каталог отдельного репозитория статей")
    fetch_parser.add_argument("--library-url", default="", help="адрес репозитория статей на GitHub")
    fetch_parser.add_argument("--queries", type=Path, default=None)
    fetch_parser.add_argument("--pause", type=float, default=0.25, help="пауза между скачиваниями, секунды")

    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            return _cmd_search(args)
        if args.command == "presets":
            return _cmd_presets(args)
        if args.command == "fetch":
            return _cmd_fetch(args)
        return _cmd_list(args)
    except (SearchError, OSError, ValueError) as exc:
        print(f"ошибка: {exc}", file=sys.stderr)
        return 1


def _cmd_search(args: argparse.Namespace) -> int:
    papers = search(args.query, limit=args.limit, query_id=args.query_id, sort=args.sort)
    write_csv(args.out, papers)
    print(f"{len(papers)} записей → {args.out}")
    return 0


def _cmd_presets(args: argparse.Namespace) -> int:
    presets = load_presets(args.queries)
    grouped = []
    all_papers = []
    for preset in presets:
        papers = search(preset.query, limit=args.limit, query_id=preset.id, sort=args.sort)
        grouped.append((preset, papers))
        all_papers.extend(papers)
        write_csv(args.out_dir / f"{preset.id}.csv", papers)
        print(f"{preset.id}: {len(papers)}")
    write_csv(args.out_dir / "all.csv", all_papers)
    write_csv(args.out_dir / "unique.csv", dedupe(all_papers))
    bibliography = args.out_dir / "bibliography.md"
    write_bibliography(
        bibliography,
        with_added(grouped, args.out_dir),
        generated_on=date.today().isoformat(),
        limit=args.limit,
        availability=load_availability(args.out_dir / "files.json"),
    )
    print(f"библиография → {bibliography}")
    print(f"уникальных статей: {len(dedupe(all_papers))}")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    presets = load_presets(args.queries)
    items = run_fetch(
        args.out_dir,
        args.library,
        presets,
        pause_s=args.pause,
        generated_on=date.today().isoformat(),
        library_url=args.library_url,
    )
    saved = sum(1 for record in items.values() if record.get("status") == "saved")
    missing = len(items) - saved
    print(f"сохранено файлов: {saved}")
    print(f"скачивание невозможно: {missing}")
    print(f"полка → {args.library}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for preset in load_presets(args.queries):
        print(f"[{preset.id}] {preset.title}")
        print(preset.question)
        print(preset.query)
        print()
    return 0
