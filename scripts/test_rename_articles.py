# -*- coding: utf-8 -*-
"""Tests for daily article renaming."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.rename_articles import (
    LEDGER_NAME,
    extract_title,
    filename_for_title,
    rename_articles,
)


def _docx(path: Path, title: str) -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        f"<w:p><w:r><w:t>{title}</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Body</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


class RenameArticlesTest(unittest.TestCase):
    def test_filename_keeps_heading_text(self) -> None:
        self.assertEqual(
            filename_for_title("In vitro maturation (IVM): краткий обзор", ".docx"),
            "In vitro maturation (IVM): краткий обзор.docx",
        )

    def test_renames_docx_and_skips_it_after_heading_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "draft.docx"
            _docx(source, "Первая статья")
            (root / "notes.py").write_text('PATH = "draft.docx"\n', encoding="utf-8")

            renamed = rename_articles(root)

            self.assertEqual(renamed, [("draft.docx", "Первая статья.docx")])
            self.assertTrue((root / "Первая статья.docx").is_file())
            self.assertFalse(source.exists())
            self.assertIn("Первая статья.docx", (root / "notes.py").read_text(encoding="utf-8"))
            self.assertEqual(extract_title(root / "Первая статья.docx"), "Первая статья")

            _docx(root / "Первая статья.docx", "Другое заглавие")
            again = rename_articles(root)

            self.assertEqual(again, [])
            self.assertTrue((root / "Первая статья.docx").is_file())
            self.assertFalse((root / "Другое заглавие.docx").exists())
            ledger = json.loads((root / LEDGER_NAME).read_text(encoding="utf-8"))
            self.assertEqual(ledger["renamed"][0]["from"], "draft.docx")
            self.assertEqual(ledger["renamed"][0]["to"], "Первая статья.docx")

    def test_markdown_article_is_renamed_and_readme_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "story.md").write_text("# Ночная тема\n\nТекст\n", encoding="utf-8")
            (root / "README.md").write_text("# Не статья\n", encoding="utf-8")

            renamed = rename_articles(root)

            self.assertEqual(renamed, [("story.md", "Ночная тема.md")])
            self.assertTrue((root / "README.md").is_file())
            self.assertTrue((root / "Ночная тема.md").is_file())

    def test_second_article_with_same_heading_gets_a_distinct_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _docx(root / "one.docx", "Общая")
            rename_articles(root)
            _docx(root / "two.docx", "Общая")

            renamed = rename_articles(root)

            self.assertEqual(renamed, [("two.docx", "Общая (2).docx")])
            self.assertTrue((root / "Общая.docx").is_file())
            self.assertTrue((root / "Общая (2).docx").is_file())


if __name__ == "__main__":
    unittest.main()
