"""Скачивание открытых файлов и пометка в списке литературы."""

from __future__ import annotations

import io
import json
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from knizhny_cherv.export import file_note, write_bibliography, write_csv
from knizhny_cherv.fetch import run_fetch
from knizhny_cherv.fulltext import europepmc_file_urls, sniff_format, unpaywall_file_urls
from knizhny_cherv.models import Paper
from knizhny_cherv.presets import Preset
from knizhny_cherv.shelf import article_basename, assert_library_is_separate


def _paper(**kwargs) -> Paper:
    base = dict(
        query_id="biology;indications",
        pmid="1",
        pmcid="PMC1",
        doi="10.1/saved",
        year="2024",
        title="Human oocyte IVM",
        authors="Das M, Son W.",
        journal="J",
        cited_by=1,
        open_access=True,
        pub_types="review",
        abstract="Abs",
        url="https://doi.org/10.1/saved",
    )
    base.update(kwargs)
    return Paper(**base)


def _docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", "<w:document/>")
    return buffer.getvalue()


class _Response:
    def __init__(self, body: bytes, content_type: str, url: str):
        self._body = body
        self.headers = {"Content-Type": content_type}
        self._url = url

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            data, self._body = self._body, b""
            return data
        data, self._body = self._body[:size], self._body[size:]
        return data

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SniffTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(sniff_format(b"%PDF-1.7\n"), "pdf")
        self.assertEqual(sniff_format(b"AT&TFORM\x00\x00\x00\x00DJVM"), "djvu")
        self.assertEqual(sniff_format(_docx()), "docx")
        self.assertIsNone(sniff_format(b"<!DOCTYPE html><html></html>"))
        self.assertIsNone(sniff_format(b"PK\x03\x04not-a-docx"))

    def test_open_urls_only(self):
        raw = {
            "fullTextUrlList": {
                "fullTextUrl": [
                    {"availabilityCode": "S", "documentStyle": "pdf", "url": "https://publisher.example/pay.pdf"},
                    {
                        "availabilityCode": "OA",
                        "documentStyle": "pdf",
                        "url": "https://files.example.test/a.pdf",
                    },
                ]
            }
        }
        self.assertEqual(europepmc_file_urls(raw), ["https://files.example.test/a.pdf"])
        urls = unpaywall_file_urls(
            {
                "best_oa_location": {
                    "url_for_pdf": "https://files.example.test/a.pdf",
                    "url": "https://repo.example.test/record/1",
                },
                "oa_locations": [
                    {"url_for_pdf": "", "url": "https://doi.org/10.1/saved"},
                    {"url_for_pdf": "https://sci-hub.example/a.pdf", "url": ""},
                ],
            }
        )
        self.assertEqual(urls[0], "https://files.example.test/a.pdf")
        self.assertIn("https://repo.example.test/record/1", urls)
        self.assertNotIn("https://doi.org/10.1/saved", urls)
        self.assertFalse(any("sci-hub" in url for url in urls))


class ShelfTests(unittest.TestCase):
    def test_basename_and_separate_library(self):
        name = article_basename(_paper(), "pdf")
        self.assertEqual(name, "2024_Das_PMC1.pdf")
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "review"
            (root / ".git").mkdir(parents=True)
            with self.assertRaises(ValueError):
                assert_library_is_separate(root / "articles", root)
            assert_library_is_separate(Path(tmp) / "ivm-articles", root)


class FetchTests(unittest.TestCase):
    def test_saves_pdf_and_marks_impossible_downloads(self):
        saved = _paper()
        closed = _paper(
            query_id="safety",
            pmid="2",
            pmcid="",
            doi="10.1/closed",
            title="Closed paper",
            authors="Liu M.",
            url="https://doi.org/10.1/closed",
            open_access=False,
        )
        via_html = _paper(
            query_id="protocols",
            pmid="3",
            pmcid="",
            doi="10.1/repo",
            title="Repository copy",
            authors="Vuong L.",
            url="https://doi.org/10.1/repo",
        )
        calls = []

        def opener(request, timeout=0):
            url = request.full_url
            calls.append(url)
            if "europepmc" in url and "PMC1" in url:
                body = {
                    "resultList": {
                        "result": [
                            {
                                "title": saved.title,
                                "fullTextUrlList": {
                                    "fullTextUrl": [
                                        {
                                            "availabilityCode": "OA",
                                            "documentStyle": "pdf",
                                            "url": "https://files.example.test/a.pdf",
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
                return _Response(json.dumps(body).encode(), "application/json", url)
            if "europepmc" in url:
                return _Response(b'{"resultList":{"result":[]}}', "application/json", url)
            if "unpaywall.org" in url and "10.1%2Frepo" in url:
                body = {"oa_locations": [{"url": "https://repo.example.test/record/9", "url_for_pdf": ""}]}
                return _Response(json.dumps(body).encode(), "application/json", url)
            if "unpaywall.org" in url:
                return _Response(b'{"oa_locations":[]}', "application/json", url)
            if url == "https://files.example.test/a.pdf":
                return _Response(b"%PDF-1.4\n", "application/pdf", url)
            if url == "https://repo.example.test/record/9":
                html = b'<html><a href="/files/b.pdf">pdf</a></html>'
                return _Response(html, "text/html", url)
            if url == "https://repo.example.test/files/b.pdf":
                return _Response(b"%PDF-1.7\n", "application/pdf", url)
            raise AssertionError(url)

        preset_biology = Preset("biology", "Биология и определение", "Что это?", "IVM")
        preset_indications = Preset("indications", "Показания", "Кому?", "IVM")
        preset_protocols = Preset("protocols", "Протоколы и культура", "Как?", "IVM")
        preset_safety = Preset("safety", "Безопасность", "Исходы?", "IVM")
        presets = [preset_biology, preset_indications, preset_protocols, preset_safety]

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "literature"
            library = root / "ivm-articles"
            write_csv(out / "unique.csv", [saved, closed, via_html])
            write_csv(out / "biology.csv", [saved])
            write_csv(out / "indications.csv", [saved])
            write_csv(out / "safety.csv", [closed])
            write_csv(out / "protocols.csv", [via_html])
            items = run_fetch(
                out,
                library,
                presets,
                opener=opener,
                pause_s=0,
                generated_on="2026-10-08",
                library_url="https://github.com/Tartartal/ivm-articles",
                start=root,
            )
            saved_path = library / "biology" / "2024_Das_PMC1.pdf"
            repo_path = library / "protocols" / "2024_Vuong_PMID3.pdf"
            self.assertTrue(saved_path.read_bytes().startswith(b"%PDF"))
            self.assertTrue(repo_path.is_file())
            self.assertEqual(items[saved.key()]["status"], "saved")
            self.assertEqual(items[saved.key()]["path"], "biology/2024_Das_PMC1.pdf")
            self.assertEqual(items[closed.key()]["status"], "unavailable")
            self.assertIn("нет открытой ссылки", items[closed.key()]["reason"])
            self.assertEqual(items[via_html.key()]["path"], "protocols/2024_Vuong_PMID3.pdf")

            bibliography = (out / "bibliography.md").read_text(encoding="utf-8")
            self.assertIn("- Файл: pdf, репозиторий статей, `biology/2024_Das_PMC1.pdf`", bibliography)
            self.assertIn("- Файл: скачивание невозможно (нет открытой ссылки на pdf, docx или djvu)", bibliography)
            self.assertIn("скачивание невозможно", file_note(closed, items))
            catalog = (library / "CATALOG.md").read_text(encoding="utf-8")
            self.assertIn("## Показания", catalog)
            self.assertIn("`biology/2024_Das_PMC1.pdf` (файл в папке `biology`)", catalog)
            self.assertIn("Файлов пока нет.", catalog)
            stored = json.loads((out / "files.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["library_url"], "https://github.com/Tartartal/ivm-articles")

            calls.clear()
            run_fetch(
                out,
                library,
                presets,
                opener=opener,
                pause_s=0,
                generated_on="2026-10-08",
                start=root,
            )
            self.assertFalse(any(url.endswith("/a.pdf") or url.endswith("/b.pdf") for url in calls))

            write_bibliography(
                out / "plain.md",
                [(preset_biology, [saved])],
                generated_on="2026-10-08",
                limit=5,
            )
            plain = (out / "plain.md").read_text(encoding="utf-8")
            self.assertNotIn("Файл:", plain)


if __name__ == "__main__":
    unittest.main()
