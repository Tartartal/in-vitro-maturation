"""Полный текст статьи из Europe PMC."""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Any

from knizhny_cherv.europepmc import USER_AGENT, SearchError, search

FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"


class FullTextError(SearchError):
    """Полный текст не скачался."""


def fetch_fulltext_xml(
    *,
    pmcid: str = "",
    pmid: str = "",
    opener: Any | None = None,
) -> tuple[str, str]:
    """Вернуть XML и подпись источника (`PMC…`)."""
    if pmcid and pmid:
        raise FullTextError("укажите что-то одно: PMCID или PMID")
    resolved = _norm_pmcid(pmcid) if pmcid else ""
    if not resolved and pmid:
        resolved = _pmcid_for_pmid(pmid, opener)
    if not resolved:
        raise FullTextError("нужен PMCID или PMID")
    return _download(resolved, opener), resolved


def _norm_pmcid(value: str) -> str:
    token = value.strip().upper()
    if token.startswith("PMC"):
        token = token[3:]
    if not token.isdigit():
        raise FullTextError(f"не похоже на PMCID: {value}")
    return "PMC" + token


def _pmcid_for_pmid(pmid: str, opener: Any | None) -> str:
    token = pmid.strip()
    if not token.isdigit():
        raise FullTextError(f"не похоже на PMID: {pmid}")
    papers = search(
        f"EXT_ID:{token} AND SRC:MED",
        limit=5,
        opener=opener,
        pause_s=0,
    )
    for paper in papers:
        if paper.pmid == token and paper.pmcid:
            return _norm_pmcid(paper.pmcid)
    for paper in papers:
        if paper.pmcid:
            return _norm_pmcid(paper.pmcid)
    raise FullTextError(f"у PMID {token} нет полного текста в PMC")


def _download(pmcid: str, opener: Any | None) -> str:
    url = FULLTEXT_URL.format(pmcid=pmcid)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml"})
    fetch = opener or urllib.request.urlopen
    try:
        with fetch(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        if exc.code == 404:
            raise FullTextError(
                f"полного текста {pmcid} нет в Europe PMC. Сохраните статью в файл и передайте его Прозектору."
            ) from exc
        raise FullTextError(f"Europe PMC HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise FullTextError(f"Europe PMC недоступен: {exc.reason}") from exc
    xml = body.decode("utf-8", errors="replace")
    if "<article" not in xml.lower():
        raise FullTextError(f"Europe PMC не вернул XML статьи для {pmcid}")
    return xml
