"""Командная строка Книжного червя."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from knizhny_cherv.europepmc import SearchError, search
from knizhny_cherv.export import dedupe, write_bibliography, write_csv
from knizhny_cherv.fulltext import fetch_fulltext_xml
from knizhny_cherv.presets import load_presets
from knizhny_cherv.prozektor import parse_article, prozektor_of, write_markdown, write_quotes_csv


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="knizhny-cherv",
        description="Поиск литературы по in vitro maturation и разбор статей Прозектором.",
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

    prozektor_parser = sub.add_parser(
        "prozektor",
        help="Прозектор: таблицы дословных цитат из статьи",
    )
    prozektor_parser.add_argument("file", nargs="?", type=Path, help="файл статьи: .txt, .md или JATS XML")
    prozektor_parser.add_argument("--pmcid", help="скачать полный текст из Europe PMC")
    prozektor_parser.add_argument("--pmid", help="найти PMCID по PMID и скачать полный текст")
    prozektor_parser.add_argument("--out", type=Path, required=True, help="Markdown с таблицами")
    prozektor_parser.add_argument("--csv", type=Path, default=None, help="те же цитаты в CSV")

    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            return _cmd_search(args)
        if args.command == "presets":
            return _cmd_presets(args)
        if args.command == "prozektor":
            return _cmd_prozektor(args)
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
        grouped,
        generated_on=date.today().isoformat(),
        limit=args.limit,
    )
    print(f"библиография → {bibliography}")
    print(f"уникальных статей: {len(dedupe(all_papers))}")
    return 0


def _cmd_prozektor(args: argparse.Namespace) -> int:
    sources = [bool(args.file), bool(args.pmcid), bool(args.pmid)]
    if sum(sources) != 1:
        raise ValueError("нужен один источник: файл, --pmcid или --pmid")
    if args.file:
        text = args.file.read_text(encoding="utf-8")
        source = str(args.file)
    else:
        text, source = fetch_fulltext_xml(pmcid=args.pmcid or "", pmid=args.pmid or "")
    prozektor = prozektor_of(parse_article(text, source=source))
    write_markdown(args.out, prozektor)
    if args.csv:
        write_quotes_csv(args.csv, prozektor)
    counts = {bucket: len(prozektor.by_bucket(bucket)) for bucket in (
        "experiment",
        "control",
        "literature",
        "results",
        "protocol",
    )}
    print(
        "структура {experiment}, контроль {control}, литобзор {literature}, "
        "результаты {results}, протоколы {protocol}".format(**counts)
    )
    print(f"прозектор → {args.out}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for preset in load_presets(args.queries):
        print(f"[{preset.id}] {preset.title}")
        print(preset.question)
        print(preset.query)
        print()
    return 0
