"""Interfaz de adapter de fuente. Permite sumar Zonaprop/Argenprop a futuro."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Listing


class SourceAdapter(ABC):
    name: str
    #: selector que indica que la página de búsqueda renderizó (para fetch.get)
    search_wait_selector: str | None = None
    #: selector que indica que la página de detalle renderizó
    detail_wait_selector: str | None = None

    @abstractmethod
    def search_urls(self) -> list[str]:
        """URLs de búsqueda a recorrer (una por barrio/tipo)."""

    @abstractmethod
    def parse_search(self, html: str, search_url: str) -> list[Listing]:
        """Extrae las cards de una página de resultados."""

    @abstractmethod
    def parse_detail(self, html: str, listing: Listing) -> Listing:
        """Enriquece una Listing con datos de su página de detalle."""
