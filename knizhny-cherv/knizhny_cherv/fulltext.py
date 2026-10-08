"""Поиск и скачивание открытого полного текста: pdf, docx или djvu."""

from __future__ import annotations

import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any

from knizhny_cherv.europepmc import SearchError, first_raw
from knizhny_cherv.models import Paper

USER_AGENT = "knizhny-cherv/0.2 (IVM literature review; mailto:ivm-review@users.noreply.github.com)"
UNPAYWALL_EMAIL = "ivm-review@users.noreply.github.com"
MAX_DOCUMENT_BYTES = 40_000_000
MAX_HTML_BYTES = 500_000
_FILE_EXT = (".pdf", ".docx", ".djvu")
_HREF = re.compile(
    r"""href\s*=\s*["']([^"']+\.(?:pdf|docx|djvu)(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)
_SKIP_LANDING = (
    "doi.org",
    "dx.doi.org",
    "pubmed.ncbi.nlm.nih.gov",
)
_BLOCKED = ("sci-hub", "libgen", "annas-archive", "z-lib.org", "zlib")


class FetchError(RuntimeError):
    """Эту ссылку нельзя сохранить как статью."""


@dataclass(frozen=True)
class AcquireResult:
    status: str
    format: str
    source_url: str
    reason: str
    data: bytes


def sniff_format(data: bytes) -> str | None:
    """Узнать pdf, docx или djvu по содержимому, а не по заголовку ответа."""
    sample = data[:16].lstrip()
    if sample.startswith(b"%PDF"):
        return "pdf"
    if sample.startswith(b"AT&T"):
        return "djvu"
    if _is_docx(data):
        return "docx"
    return None


def europepmc_file_urls(raw: dict[str, Any]) -> list[str]:
    block = raw.get("fullTextUrlList") or {}
    items = block.get("fullTextUrl") or []
    if isinstance(items, dict):
        items = [items]
    urls: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _is_open(item):
            continue
        url = str(item.get("url") or "").strip()
        style = str(item.get("documentStyle") or "").lower()
        if not url or not _allowed(url):
            continue
        if style in {"pdf", "docx", "doc", "djvu"} or _ext(url) in _FILE_EXT:
            urls.append(url)
    return urls


def unpaywall_file_urls(payload: dict[str, Any]) -> list[str]:
    locations: list[dict[str, Any]] = []
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    extra = payload.get("oa_locations") or []
    if isinstance(extra, dict):
        extra = [extra]
    if isinstance(extra, list):
        locations.extend(item for item in extra if isinstance(item, dict))

    direct: list[str] = []
    landings: list[str] = []
    seen: set[str] = set()
    for loc in locations:
        pdf = str(loc.get("url_for_pdf") or "").strip()
        page = str(loc.get("url") or "").strip()
        for url in (pdf, page):
            if not url or url in seen or not _allowed(url):
                continue
            seen.add(url)
            if url == pdf or _ext(url) in _FILE_EXT or "/pdf" in urllib.parse.urlparse(url).path.lower():
                direct.append(url)
            elif not _skips_landing(url):
                landings.append(url)
    return direct + landings


def acquire(paper: Paper, opener: Any) -> AcquireResult:
    """Скачать открытую копию или вернуть причину, почему это невозможно."""
    urls = _candidate_urls(paper, opener)
    if not urls:
        return AcquireResult(
            status="unavailable",
            format="",
            source_url="",
            reason="нет открытой ссылки на pdf, docx или djvu",
            data=b"",
        )
    for url in urls[:12]:
        try:
            data, fmt, final = _try_url(url, opener)
        except FetchError:
            continue
        return AcquireResult(status="saved", format=fmt, source_url=final, reason="", data=data)
    return AcquireResult(
        status="unavailable",
        format="",
        source_url="",
        reason="открытые ссылки не отдали файл pdf, docx или djvu",
        data=b"",
    )


def _candidate_urls(paper: Paper, opener: Any) -> list[str]:
    urls: list[str] = []
    query = _record_query(paper)
    if query:
        try:
            raw = first_raw(query, opener=opener)
        except SearchError:
            raw = None
        if raw:
            urls.extend(europepmc_file_urls(raw))
    if paper.doi:
        payload = _unpaywall(paper.doi, opener)
        if payload:
            urls.extend(unpaywall_file_urls(payload))
    unique: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


def _record_query(paper: Paper) -> str:
    if paper.pmcid:
        return f"PMCID:{paper.pmcid}"
    if paper.doi:
        return f'DOI:"{paper.doi}"'
    if paper.pmid:
        return f"EXT_ID:{paper.pmid} AND SRC:MED"
    return ""


def _unpaywall(doi: str, opener: Any) -> dict[str, Any] | None:
    url = (
        "https://api.unpaywall.org/v2/"
        + urllib.parse.quote(doi, safe="")
        + "?email="
        + urllib.parse.quote(UNPAYWALL_EMAIL)
    )
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _try_url(url: str, opener: Any, *, depth: int = 0) -> tuple[bytes, str, str]:
    if not _allowed(url):
        raise FetchError("ссылка отклонена")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*;q=0.5",
        },
    )
    try:
        with opener(request, timeout=60) as response:
            content_type = ""
            headers = getattr(response, "headers", None)
            if headers is not None:
                content_type = str(headers.get("Content-Type") or "")
            limit = MAX_HTML_BYTES if "html" in content_type.lower() else MAX_DOCUMENT_BYTES
            data, truncated = _read_limited(response, limit)
            final = response.geturl() if hasattr(response, "geturl") else url
    except urllib.error.HTTPError as exc:
        raise FetchError(f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FetchError("сеть недоступна") from exc
    except TimeoutError as exc:
        raise FetchError("таймаут") from exc

    if truncated and "html" not in content_type.lower() and not _looks_html(data):
        raise FetchError("файл больше 40 МБ")
    fmt = sniff_format(data)
    if fmt and not truncated:
        return data, fmt, str(final)
    if depth == 0 and (_looks_html(data) or "html" in content_type.lower()):
        html = data.decode("utf-8", errors="replace")
        for link in _same_host_files(html, str(final))[:4]:
            try:
                return _try_url(link, opener, depth=1)
            except FetchError:
                continue
    raise FetchError("ответ не pdf, docx или djvu")


def _read_limited(response: Any, limit: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    while True:
        block = response.read(65536)
        if not block:
            break
        chunks.append(block)
        total += len(block)
        if total > limit:
            return b"".join(chunks), True
    return b"".join(chunks), False


def _same_host_files(html: str, page_url: str) -> list[str]:
    base = urllib.parse.urlparse(page_url)
    found: list[str] = []
    for href in _HREF.findall(html):
        absolute = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc != base.netloc or not _allowed(absolute):
            continue
        if absolute not in found:
            found.append(absolute)
    return found


def _is_open(item: dict[str, Any]) -> bool:
    code = str(item.get("availabilityCode") or "").upper()
    if code in {"OA", "F"}:
        return True
    text = str(item.get("availability") or "").lower()
    return text.startswith("open") or text.startswith("free")


def _ext(url: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    for ext in _FILE_EXT:
        if path.endswith(ext):
            return ext
    return ""


def _allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    return not any(part in host for part in _BLOCKED)


def _skips_landing(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(host == name or host.endswith("." + name) for name in _SKIP_LANDING)


def _looks_html(data: bytes) -> bool:
    sample = data[:200].lstrip().lower()
    return sample.startswith(b"<!doctype") or sample.startswith(b"<html") or sample.startswith(b"<head")


def _is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "word/document.xml" in names
