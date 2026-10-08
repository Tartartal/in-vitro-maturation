"""Разбор статьи: цитаты остаются дословными и расходятся по таблицам."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from knizhny_cherv.cli import main
from knizhny_cherv.fulltext import FullTextError, fetch_fulltext_xml
from knizhny_cherv.razbor import (
    classify,
    parse_article,
    razbor_of,
    render_markdown,
    split_sentences,
    strip_citations,
)


ARTICLE = """
# Unstimulated IVM and conventional IVF

## Introduction

In vitro maturation has been shown to reduce OHSS risk in women with PCOS (Smith et al., 2020). Previous studies reported live birth rates around 30% [2]. We aimed to compare unstimulated IVM with conventional IVF.

## Materials and methods

### Study design

This retrospective cohort study included women aged 20-40 years treated between January 2018 and December 2020. The study protocol was approved by the ethics committee. Written informed consent was obtained from all participants.

### Participants

Eligible participants were women diagnosed with PCOS. The study group comprised 100 women who underwent unstimulated IVM. A control group was established from 300 women undergoing conventional IVF, matched for age. Controls were selected using a 1:3 ratio. Exclusion criteria were oocyte donation cycles and PGT.

### IVM protocol

Oocytes were retrieved with a 19-gauge needle at 80 mmHg. Immature COCs were cultured in IVM medium supplemented with 0.075 IU/mL FSH for 30 h. Metaphase II oocytes were fertilized via ICSI.

### Statistical analysis

Continuous variables are presented as mean ± SD. Kaplan-Meier analysis was employed to estimate cumulative live birth. All statistical analyses were performed using SPSS version 27. A P-value of < 0.05 was considered statistically significant.

## Results

The live birth rate was significantly lower after IVM than IVF (22.0% vs. 48.0%; P < 0.001). No cases of OHSS occurred in the IVM group. Of the 400 women scheduled for treatment, 100 met the inclusion criteria (Fig. 1).

## Discussion

Our findings differ from previous reports of higher success [4]. Smith et al. described similar safety findings.

## References

1. Smith A. Some paper about oocytes. 2020.
"""


JATS = """<?xml version="1.0"?>
<article>
  <front>
    <article-meta>
      <title-group><article-title>IVM <italic>cohort</italic></article-title></title-group>
      <abstract>
        <sec><title>Background</title><p>IVM has been shown to help women with PCOS (Smith et al., 2020).</p></sec>
        <sec><title>Methods</title><p>This retrospective cohort study included women aged 20-40 years.</p></sec>
        <sec><title>Results</title><p>The live birth rate was 22.0% (P &lt; 0.001).</p></sec>
      </abstract>
    </article-meta>
  </front>
  <body>
    <sec><title>Introduction</title><p>Previous studies reported a rate around 30% [2].</p></sec>
    <sec><title>Materials and methods</title>
      <sec><title>Participants</title><p>A control group was established from women undergoing IVF.</p></sec>
      <sec><title>IVM protocol</title><p>COCs were cultured in IVM medium supplemented with 0.075 IU/mL FSH for 30 h.</p></sec>
    </sec>
    <sec><title>Results</title><p>No cases of OHSS occurred in the IVM group.</p></sec>
    <sec sec-type="ref-list"><title>References</title><p>Some paper about oocytes.</p></sec>
  </body>
</article>
"""


RUSSIAN = """
# Созревание ооцитов

## Введение

Ранее было показано, что IVM снижает риск СГЯ [1].

## Методы

В настоящем исследовании мы включили 40 женщин с СПКЯ. Контрольная группа получала стандартный протокол ЭКО.

## Протокол IVM

Ооциты культивировали в среде созревания в течение 30 ч.

## Результаты

Частота созревания составила 60% (P < 0.05).

## Литература

1. Иванов И. Статья про ооциты. 2020.
"""


def _texts(razbor, bucket: str) -> list[str]:
    return [quote.text for quote in razbor.by_bucket(bucket)]


class SentenceTests(unittest.TestCase):
    def test_keeps_decimals_and_figure_abbreviations(self):
        parts = split_sentences("The rate was 10.5% vs. 12.0% (Fig. 1). No cases followed.")
        self.assertEqual(
            parts,
            ["The rate was 10.5% vs. 12.0% (Fig. 1).", "No cases followed."],
        )

    def test_citation_markers_come_off_without_touching_results(self):
        plain = strip_citations(
            "Rates were lower (Smith et al., 2020) than before [9–11] (22.0% vs. 48.0%; P < 0.001)."
        )
        self.assertNotIn("Smith", plain)
        self.assertNotIn("[9", plain)
        self.assertIn("22.0%", plain)
        self.assertIn("P < 0.001", plain)
        self.assertIn("Rates were lower", plain)


class PlainArticleTests(unittest.TestCase):
    def setUp(self):
        self.document = parse_article(ARTICLE, source="article.txt")
        self.razbor = razbor_of(self.document)

    def test_quotes_are_verbatim_english(self):
        self.assertEqual(self.document.language, "en")
        self.assertEqual(self.document.completeness, "полный текст")
        self.assertIn("Unstimulated IVM", self.document.title)
        for quote in self.razbor.quotes:
            self.assertIn(quote.text, self.document.full_text)
            self.assertNotIn("Some paper about oocytes", quote.text)

    def test_buckets_follow_what_was_done(self):
        experiment = _texts(self.razbor, "experiment")
        control = _texts(self.razbor, "control")
        literature = _texts(self.razbor, "literature")
        results = _texts(self.razbor, "results")
        protocol = _texts(self.razbor, "protocol")

        self.assertTrue(any("We aimed to compare" in item for item in experiment))
        self.assertTrue(any("retrospective cohort study" in item for item in experiment))
        self.assertTrue(any("Eligible participants" in item for item in experiment))
        self.assertTrue(any("Kaplan-Meier" in item for item in experiment))
        self.assertFalse(any("ethics committee" in item.lower() for item in experiment))
        self.assertFalse(any("SPSS" in item for item in experiment))
        self.assertFalse(any("0.075 IU/mL" in item for item in experiment))

        self.assertTrue(any("control group was established" in item for item in control))
        self.assertTrue(any(item.startswith("Controls were selected") for item in control))
        self.assertFalse(any("22.0%" in item for item in control))

        self.assertTrue(any("has been shown" in item for item in literature))
        self.assertTrue(any("Previous studies reported" in item for item in literature))
        self.assertTrue(any("Smith et al. described" in item for item in literature))
        self.assertFalse(any("30%" in item and item in results for item in literature))

        self.assertTrue(any("22.0%" in item and "P < 0.001" in item for item in results))
        self.assertTrue(any(item.startswith("No cases of OHSS") for item in results))
        self.assertFalse(any("around 30%" in item for item in results))

        self.assertTrue(any("19-gauge" in item and "mmHg" in item for item in protocol))
        self.assertTrue(any("0.075 IU/mL FSH for 30 h" in item for item in protocol))
        self.assertTrue(any("fertilized via ICSI" in item for item in protocol))

    def test_plain_column_drops_markers_only(self):
        cited = next(quote for quote in self.razbor.by_bucket("literature") if "has been shown" in quote.text)
        self.assertIn("(Smith et al., 2020)", cited.text)
        self.assertNotIn("Smith", cited.plain)
        self.assertIn("has been shown to reduce OHSS risk", cited.plain)
        numbered = next(quote for quote in self.razbor.by_bucket("literature") if "[2]" in quote.text)
        self.assertIn("30%", numbered.plain)
        self.assertNotIn("[2]", numbered.plain)

    def test_markdown_tables_keep_original_wording(self):
        markdown = render_markdown(self.razbor)
        self.assertIn("## Структура эксперимента", markdown)
        self.assertIn("## Контроль", markdown)
        self.assertIn("## Данные литобзора", markdown)
        self.assertIn("## Результаты", markdown)
        self.assertIn("## Протоколы", markdown)
        self.assertIn("Oocytes were retrieved with a 19-gauge needle at 80 mmHg.", markdown)
        self.assertIn("Язык цитат: английский", markdown)
        self.assertNotIn("Some paper about oocytes", markdown)


class ClassifyEdgeTests(unittest.TestCase):
    def test_transfer_steps_leave_the_outcome_definition(self):
        outcome = "The primary outcome was the CLBR per initiated oocyte retrieval cycle."
        self.assertIn("experiment", classify(outcome, "methods", protocol=False))
        self.assertNotIn("protocol", classify(outcome, "methods", protocol=False))

        transferred = "One or two cleavage-stage embryos or a single blastocyst were transferred."
        support = (
            "Luteal support (vaginal progesterone gel 90 mg/day + oral dydrogesterone 10 mg bid) "
            "commenced on retrieval day."
        )
        self.assertEqual(classify(transferred, "methods", protocol=True), {"protocol"})
        self.assertEqual(classify(support, "methods", protocol=True), {"protocol"})

    def test_cited_rate_in_discussion_stays_with_the_literature(self):
        sentence = (
            "Indeed, as recently noted by Vuong et al. (2025), the ongoing pregnancy rate was 38.3% [27]."
        )
        buckets = classify(sentence, "discussion", protocol=False)
        self.assertIn("literature", buckets)
        self.assertNotIn("results", buckets)

    def test_outcome_threshold_is_not_a_protocol_step(self):
        sentence = "Critical OHSS was defined as renal failure with creatinine of 1.6 mg/dL."
        buckets = classify(sentence, "methods", protocol=False)
        self.assertIn("experiment", buckets)
        self.assertNotIn("protocol", buckets)

    def test_results_restatement_of_matching_stays_a_result(self):
        sentence = (
            "A total of 545 women underwent unstimulated IVM, and 1,635 matched controls underwent conventional IVF."
        )
        buckets = classify(sentence, "results", protocol=False)
        self.assertIn("results", buckets)
        self.assertNotIn("control", buckets)

    def test_table_pointer_is_not_a_result(self):
        sentence = "Outcomes of the first embryo transfer are presented in Table 3."
        self.assertEqual(classify(sentence, "results", protocol=False), set())


class JatsTests(unittest.TestCase):
    def test_sections_and_reference_list(self):
        document = parse_article(JATS, source="PMC1")
        self.assertEqual(document.title, "IVM cohort")
        razbor = razbor_of(document)
        self.assertNotIn("Some paper about oocytes", document.full_text)
        self.assertTrue(any("control group was established" in item for item in _texts(razbor, "control")))
        self.assertTrue(any("0.075 IU/mL" in item for item in _texts(razbor, "protocol")))
        self.assertTrue(any("has been shown" in item for item in _texts(razbor, "literature")))
        self.assertTrue(any("22.0%" in item for item in _texts(razbor, "results")))
        self.assertTrue(any("retrospective cohort" in item for item in _texts(razbor, "experiment")))
        self.assertTrue(any("No cases of OHSS" in item for item in _texts(razbor, "results")))


class RussianTests(unittest.TestCase):
    def test_russian_article_is_not_translated(self):
        document = parse_article(RUSSIAN, source="ru.txt")
        self.assertEqual(document.language, "ru")
        razbor = razbor_of(document)
        literature = _texts(razbor, "literature")
        experiment = _texts(razbor, "experiment")
        control = _texts(razbor, "control")
        protocol = _texts(razbor, "protocol")
        results = _texts(razbor, "results")
        self.assertTrue(any("Ранее было показано" in item for item in literature))
        self.assertTrue(any("В настоящем исследовании" in item for item in experiment))
        self.assertTrue(any("Контрольная группа" in item for item in control))
        self.assertTrue(any("культивировали" in item for item in protocol))
        self.assertTrue(any("60%" in item for item in results))
        self.assertNotIn("Статья про ооциты", document.full_text)
        cited = next(quote for quote in razbor.by_bucket("literature") if "[1]" in quote.text)
        self.assertNotIn("[1]", cited.plain)
        self.assertIn("Ранее было показано", cited.plain)


class FullTextTests(unittest.TestCase):
    def test_pmid_resolves_then_downloads_xml(self):
        seen = []

        def opener(request, timeout=0):
            seen.append(request.full_url)
            if "fullTextXML" in request.full_url:
                return _Body(JATS.encode("utf-8"))
            payload = {
                "resultList": {
                    "result": [{"pmid": "41981617", "pmcid": "PMC13200467", "title": "IVM cohort"}]
                },
                "nextCursorMark": "",
            }
            return _Body(json.dumps(payload).encode("utf-8"))

        xml, source = fetch_fulltext_xml(pmid="41981617", opener=opener)
        self.assertEqual(source, "PMC13200467")
        self.assertIn("<article", xml)
        self.assertTrue(any("fullTextXML" in url for url in seen))

    def test_missing_full_text(self):
        def opener(request, timeout=0):
            raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, io.BytesIO(b"no"))

        with self.assertRaises(FullTextError):
            fetch_fulltext_xml(pmcid="PMC1", opener=opener)


class _Body:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class CliTests(unittest.TestCase):
    def test_razbor_writes_markdown_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "article.txt"
            source.write_text(ARTICLE, encoding="utf-8")
            out = root / "razbor.md"
            csv_path = root / "razbor.csv"
            code = main(["razbor", str(source), "--out", str(out), "--csv", str(csv_path)])
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("19-gauge", text)
            table = csv_path.read_text(encoding="utf-8")
            self.assertIn("protocol", table)
            self.assertIn("0.075 IU/mL", table)
            self.assertNotIn("Some paper about oocytes", text)

    def test_razbor_requires_one_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["razbor", "--out", str(Path(tmp) / "out.md")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
