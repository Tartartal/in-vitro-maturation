"""Тесты разбора Europe PMC, пагинации и выгрузки."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from knizhny_cherv.europepmc import paper_from_raw, search
from knizhny_cherv.export import dedupe, write_bibliography, write_csv
from knizhny_cherv.models import Paper
from knizhny_cherv.presets import Preset, load_presets


def _raw(pmid: str, title: str, doi: str = "") -> dict:
    return {
        "pmid": pmid,
        "doi": doi,
        "pmcid": "PMC" + pmid,
        "title": title,
        "authorString": "Ivanov A, Petrova B.",
        "pubYear": "2024",
        "citedByCount": 3,
        "isOpenAccess": "Y",
        "abstractText": "  Краткое   резюме. ",
        "pubTypeList": {"pubType": ["Journal Article", "review"]},
        "journalInfo": {"journal": {"title": "Human Reproduction"}},
    }


class _Response:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ParseTests(unittest.TestCase):
    def test_paper_fields(self):
        paper = paper_from_raw(_raw("123", "IVM <i>review</i>", "10.1000/abc"), query_id="biology")
        self.assertEqual(paper.title, "IVM review")
        self.assertEqual(paper.query_id, "biology")
        self.assertEqual(paper.journal, "Human Reproduction")
        self.assertEqual(paper.abstract, "Краткое резюме.")
        headed = paper_from_raw({"title": "T", "abstractText": "<h4>Abstract</h4>Oocyte maturation."})
        self.assertEqual(headed.abstract, "Oocyte maturation.")
        self.assertEqual(paper.pub_types, "Journal Article; review")
        self.assertTrue(paper.open_access)
        self.assertEqual(paper.url, "https://doi.org/10.1000/abc")
        self.assertEqual(paper.key(), "doi:10.1000/abc")

    def test_title_key_when_no_ids(self):
        paper = paper_from_raw({"title": "  Same   Title "})
        self.assertEqual(paper.key(), "title:same title")
        self.assertEqual(paper.url, "")


class SearchTests(unittest.TestCase):
    def test_paginates_until_limit(self):
        pages = [
            {
                "resultList": {"result": [_raw("1", "One", "10.1/a"), _raw("2", "Two")]},
                "nextCursorMark": "cursor-2",
            },
            {
                "resultList": {"result": [_raw("3", "Three", "10.1/c")]},
                "nextCursorMark": "cursor-3",
            },
        ]

        def opener(request, timeout=0):
            self.assertIn("cursorMark=", request.full_url)
            return _Response(pages.pop(0))

        papers = search("IVM", limit=3, query_id="biology", opener=opener, pause_s=0)
        self.assertEqual([p.pmid for p in papers], ["1", "2", "3"])
        self.assertEqual(papers[0].query_id, "biology")

    def test_skips_empty_title(self):
        def opener(request, timeout=0):
            return _Response({"resultList": {"result": [{"pmid": "9", "title": "  "}]}, "nextCursorMark": ""})

        self.assertEqual(search("IVM", limit=5, opener=opener, pause_s=0), [])


class ExportTests(unittest.TestCase):
    def test_csv_markdown_and_dedupe(self):
        first = Paper(
            query_id="biology",
            pmid="1",
            pmcid="",
            doi="10.1/a",
            year="2020",
            title="Shared",
            authors="A",
            journal="J",
            cited_by=1,
            open_access=False,
            pub_types="review",
            abstract="Abs",
            url="https://doi.org/10.1/a",
        )
        second = Paper(
            query_id="safety",
            pmid="1",
            pmcid="PMC1",
            doi="10.1/A",
            year="2020",
            title="Shared",
            authors="A",
            journal="J",
            cited_by=4,
            open_access=True,
            pub_types="review",
            abstract="Abs",
            url="https://doi.org/10.1/A",
        )
        unique = dedupe([first, second])
        self.assertEqual(len(unique), 1)
        self.assertEqual(unique[0].query_id, "biology;safety")

        preset = Preset(id="biology", title="Биология", question="Что это?", query="IVM")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_csv(root / "biology.csv", [first])
            text = (root / "biology.csv").read_text(encoding="utf-8")
            self.assertIn("Shared", text)
            self.assertIn("open_access", text)
            write_bibliography(root / "bibliography.md", [(preset, [first])], generated_on="2026-10-08", limit=5)
            md = (root / "bibliography.md").read_text(encoding="utf-8")
            self.assertIn("## Биология", md)
            self.assertIn("Abs", md)


class PresetTests(unittest.TestCase):
    def test_builtin_queries_cover_review_sections(self):
        presets = load_presets()
        self.assertEqual(
            [item.id for item in presets],
            ["biology", "indications", "protocols", "efficacy", "safety"],
        )
        for preset in presets:
            self.assertTrue("in vitro maturation" in preset.query.lower() or "IVM" in preset.query)
            self.assertTrue(preset.question.endswith("?"))


if __name__ == "__main__":
    unittest.main()
