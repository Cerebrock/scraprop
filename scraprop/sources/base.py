"""Interfaz de adapter de fuente. Permite sumar Zonaprop/Argenprop a futuro."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

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

    def count_cards(self, html: str) -> int:
        """Cantidad de cards crudas en la página (incluye las que parse_search
        descarta, p.ej. emprendimientos). Se usa para avanzar la paginación."""
        return 0

    def total_results(self, html: str) -> Optional[int]:
        """Total de resultados que declara la fuente para la búsqueda, o None.
        Corta la paginación: pasado el total, ML devuelve páginas 'overflow'
        que ignoran parte de los filtros (p.ej. el polígono)."""
        return None

    def next_page_url(self, search_url: str, next_offset: int) -> Optional[str]:
        """URL de la página siguiente (next_offset = índice 1-based del primer
        ítem). None si la fuente no pagina."""
        return None
