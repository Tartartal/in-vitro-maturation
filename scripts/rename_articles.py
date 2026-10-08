# -*- coding: utf-8 -*-
"""Rename article files to the title written in their heading.

Articles already listed in article-renames.json are left untouched.
"""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

LEDGER_NAME = "article-renames.json"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ARTICLE_SUFFIXES = {".docx", ".md", ".mdx", ".markdown"}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".mdx",
    ".markdown",
    ".txt",
    ".yml",
    ".yaml",
    ".rst",
    ".html",
    ".toml",
}
SKIP_DIR_NAMES = {
    ".git",
    ".github",
    ".cursor",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
}
README_NAMES = {
    "readme.md",
    "readme.mdx",
    "readme.markdown",
    "readme.txt",
}


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parent.parent


def filename_for_title(title: str, suffix: str) -> str:
    """Build a file name from a heading, keeping the title text intact."""
    cleaned: list[str] = []
    for char in title.strip():
        if char in "\\/\0" or ord(char) < 32:
            cleaned.append(" ")
        else:
            cleaned.append(char)
    name = " ".join("".join(cleaned).split()).rstrip(". ")
    if not name:
        raise ValueError(f"heading {title!r} cannot be used as a file name")
    if len(name) > 180:
        name = name[:180].rstrip(". ")
    return name + suffix


def extract_title(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _docx_title(path)
    if suffix in {".md", ".mdx", ".markdown"}:
        return _markdown_title(path)
    return None


def _docx_title(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return None
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return None
    for paragraph in root.iter(f"{{{W_NS}}}p"):
        texts = [
            (node.text or "")
            for node in paragraph.iter(f"{{{W_NS}}}t")
        ]
        title = "".join(texts).strip()
        if title:
            return title
    return None


def _markdown_title(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    index = 0
    if lines and lines[0].strip() == "---":
        index = 1
        while index < len(lines) and lines[index].strip() != "---":
            index += 1
        index += 1
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            title = stripped[2:].strip()
            return title or None
        index += 1
    return None


def _is_skipped_dir(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_articles(root: Path) -> list[Path]:
    articles: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_skipped_dir(relative):
            continue
        if path.name.lower() in README_NAMES:
            continue
        if path.suffix.lower() not in ARTICLE_SUFFIXES:
            continue
        if path.name.startswith("~$"):
            continue
        articles.append(path)
    return sorted(articles)


def _load_ledger(path: Path) -> dict:
    if not path.exists():
        return {"renamed": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("renamed", [])
    return data


def _already_renamed(ledger: dict) -> set[str]:
    return {
        entry["to"]
        for entry in ledger["renamed"]
        if isinstance(entry, dict) and entry.get("to")
    }


def _unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    number = 2
    while True:
        candidate = target.with_name(f"{stem} ({number}){suffix}")
        if not candidate.exists():
            return candidate
        number += 1


def _move(root: Path, source: Path, dest: Path) -> None:
    if (root / ".git").exists():
        completed = subprocess.run(
            [
                "git",
                "mv",
                "--",
                source.relative_to(root).as_posix(),
                dest.relative_to(root).as_posix(),
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return
    source.rename(dest)


def _update_references(root: Path, old_rel: str, new_rel: str, ledger_path: Path) -> None:
    old_name = Path(old_rel).name
    new_name = Path(new_rel).name

    def replace_link(match: re.Match[str]) -> str:
        dest = match.group(2)
        if old_name not in dest and old_rel not in dest:
            return match.group(0)
        dest = dest.replace(old_rel, new_rel).replace(old_name, new_name).strip()
        if dest.startswith("<") and dest.endswith(">"):
            return f"]({dest})"
        return f"](<{dest}>)"

    for path in root.rglob("*"):
        if not path.is_file() or path.resolve() == ledger_path.resolve():
            continue
        relative = path.relative_to(root)
        if _is_skipped_dir(relative):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        updated = re.sub(r"(\]\()([^)\n]*)(\))", replace_link, text)
        updated = updated.replace(old_rel, new_rel).replace(old_name, new_name)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def rename_articles(root: Path | None = None) -> list[tuple[str, str]]:
    """Rename articles under root. Return (old relative path, new relative path)."""
    root = (root or repo_root_from_here()).resolve()
    ledger_path = root / LEDGER_NAME
    ledger = _load_ledger(ledger_path)
    done = _already_renamed(ledger)
    renamed: list[tuple[str, str]] = []

    for path in iter_articles(root):
        relative = path.relative_to(root).as_posix()
        if relative in done:
            print(f"skipped (already renamed): {relative}")
            continue
        title = extract_title(path)
        if not title:
            print(f"skipped (no heading): {relative}")
            continue
        dest_name = filename_for_title(title, path.suffix)
        dest = path.with_name(dest_name)
        if dest.resolve() == path.resolve():
            print(f"unchanged (name matches heading): {relative}")
            continue
        if dest.exists():
            dest = _unique_target(dest)
        old_rel = relative
        new_rel = dest.relative_to(root).as_posix()
        _move(root, path, dest)
        _update_references(root, old_rel, new_rel, ledger_path)
        entry = {
            "from": old_rel,
            "to": new_rel,
            "title": title,
            "renamed_on": date.today().isoformat(),
        }
        ledger["renamed"].append(entry)
        done.add(new_rel)
        renamed.append((old_rel, new_rel))
        print(f"renamed: {old_rel} -> {new_rel}")

    if renamed:
        ledger_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return renamed


def main() -> None:
    rename_articles(repo_root_from_here())


if __name__ == "__main__":
    main()
