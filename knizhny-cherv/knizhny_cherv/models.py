"""Запись найденной статьи."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Paper:
    query_id: str
    pmid: str
    pmcid: str
    doi: str
    year: str
    title: str
    authors: str
    journal: str
    cited_by: int
    open_access: bool
    pub_types: str
    abstract: str
    url: str

    def key(self) -> str:
        if self.doi:
            return "doi:" + self.doi.lower()
        if self.pmid:
            return "pmid:" + self.pmid
        if self.pmcid:
            return "pmcid:" + self.pmcid
        return "title:" + " ".join(self.title.lower().split())
