"""Клиент Europe PMC REST API (без сторонних библиотек)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from knizhny_cherv.models import Paper

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "knizhny-cherv/0.1 (IVM literature review)"
SORTS = {
    "relevance": None,
    "cited": "CITED desc",
    "date": "P_PDATE_D desc",
}


class SearchError(RuntimeError):
    """Europe PMC не ответил или вернул ошибку."""


def search(
    query: str,
    *,
    limit: int = 25,
    query_id: str = "",
    sort: str = "relevance",
    opener: Any | None = None,
    pause_s: float = 0.2,
) -> list[Paper]:
    """Вернуть до `limit` статей. `opener` — подмена urlopen в тестах."""
    if limit < 1:
        raise ValueError("limit должен быть не меньше 1")
    if sort not in SORTS:
        raise ValueError(f"неизвестная сортировка: {sort}")

    fetch = opener or urllib.request.urlopen
    papers: list[Paper] = []
    cursor = "*"
    seen_cursors = {cursor}

    while len(papers) < limit:
        page_size = min(100, limit - len(papers))
        payload = _get_page(fetch, query, page_size, cursor, SORTS[sort])
        result_list = (payload.get("resultList") or {}).get("result") or []
        if isinstance(result_list, dict):
            result_list = [result_list]
        if not result_list:
            break
        for raw in result_list:
            paper = paper_from_raw(raw, query_id=query_id)
            if paper.title:
                papers.append(paper)
            if len(papers) >= limit:
                break
        next_cursor = payload.get("nextCursorMark") or ""
        if not next_cursor or next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor
        if pause_s and opener is None:
            time.sleep(pause_s)
    return papers


def first_raw(query: str, *, opener: Any | None = None) -> dict[str, Any] | None:
    """Первая запись Europe PMC с полными полями, включая ссылки на текст."""
    fetch = opener or urllib.request.urlopen
    payload = _get_page(fetch, query, 1, "*", None)
    result_list = (payload.get("resultList") or {}).get("result") or []
    if isinstance(result_list, dict):
        result_list = [result_list]
    if not result_list or not isinstance(result_list[0], dict):
        return None
    return result_list[0]


def paper_from_raw(raw: dict[str, Any], *, query_id: str = "") -> Paper:
    doi = str(raw.get("doi") or "").strip()
    pmid = str(raw.get("pmid") or "").strip()
    pmcid = str(raw.get("pmcid") or "").strip()
    cited = raw.get("citedByCount") or 0
    try:
        cited_by = int(cited)
    except (TypeError, ValueError):
        cited_by = 0
    pub_types = _pub_types(raw.get("pubTypeList"))
    return Paper(
        query_id=query_id,
        pmid=pmid,
        pmcid=pmcid,
        doi=doi,
        year=str(raw.get("pubYear") or "").strip(),
        title=_clean(str(raw.get("title") or "")),
        authors=_authors(raw),
        journal=_journal(raw),
        cited_by=cited_by,
        open_access=str(raw.get("isOpenAccess") or "").upper() == "Y",
        pub_types=pub_types,
        abstract=_clean(str(raw.get("abstractText") or "")),
        url=_url(doi, pmid, pmcid),
    )


def _get_page(fetch: Any, query: str, page_size: int, cursor: str, sort: str | None) -> dict[str, Any]:
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(page_size),
        "resultType": "core",
        "cursorMark": cursor,
    }
    if sort:
        params["sort"] = sort
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with fetch(request, timeout=45) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SearchError(f"Europe PMC HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SearchError(f"Europe PMC недоступен: {exc.reason}") from exc
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SearchError("Europe PMC вернул не JSON") from exc
    if not isinstance(payload, dict):
        raise SearchError("Europe PMC вернул неожиданный ответ")
    return payload


def _authors(raw: dict[str, Any]) -> str:
    author_string = str(raw.get("authorString") or "").strip()
    if author_string:
        return _clean(author_string)
    authors = (raw.get("authorList") or {}).get("author") or []
    if isinstance(authors, dict):
        authors = [authors]
    names: list[str] = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        full = str(author.get("fullName") or "").strip()
        if not full:
            full = " ".join(
                part
                for part in (str(author.get("firstName") or "").strip(), str(author.get("lastName") or "").strip())
                if part
            )
        if full:
            names.append(full)
    return ", ".join(names)


def _journal(raw: dict[str, Any]) -> str:
    info = raw.get("journalInfo") or {}
    if not isinstance(info, dict):
        return ""
    journal = info.get("journal") or {}
    if not isinstance(journal, dict):
        return ""
    return str(journal.get("title") or journal.get("isoabbreviation") or "").strip()


def _pub_types(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    types = value.get("pubType") or []
    if isinstance(types, str):
        types = [types]
    if not isinstance(types, list):
        return ""
    return "; ".join(str(item).strip() for item in types if str(item).strip())


def _url(doi: str, pmid: str, pmcid: str) -> str:
    if doi:
        return "https://doi.org/" + doi
    if pmid:
        return "https://europepmc.org/article/MED/" + pmid
    if pmcid:
        return "https://europepmc.org/article/PMC/" + pmcid
    return ""


_TAGS = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = " ".join(_TAGS.sub(" ", text).replace("\xa0", " ").split())
    if text.lower().startswith("abstract "):
        text = text[len("abstract ") :]
    return text
