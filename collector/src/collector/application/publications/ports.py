"""Porta para obter uma página. Sem detalhes de transporte HTTP."""

from __future__ import annotations

from typing import Protocol

from collector.application.publications.query import PublicationQuery
from collector.application.publications.results import PublicationPage


class PublicationPageFetcher(Protocol):
    def fetch_page(self, query: PublicationQuery, page: int) -> PublicationPage:
        """Devolve exatamente uma página da consulta."""
