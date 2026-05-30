"""Modelos de datos compartidos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Listing:
    """Una publicación de propiedad (datos crudos del scraper, antes del LLM)."""
    source: str                 # "mercadolibre"
    listing_id: str             # ej "MLA-1234567890"
    url: str
    title: Optional[str] = None
    price: Optional[float] = None        # valor numérico tal cual aparece
    currency: Optional[str] = None       # "USD" | "ARS"
    surface_m2: Optional[int] = None     # superficie total si se pudo parsear
    rooms: Optional[int] = None          # ambientes
    neighbourhood_raw: Optional[str] = None  # ubicación tal cual la muestra ML
    address: Optional[str] = None
    description: Optional[str] = None     # texto completo para el LLM
    image: Optional[str] = None
    posted_days_ago: Optional[int] = None  # antigüedad de la publicación en días
    status: Optional[str] = None           # activa | pausada | finalizada | no disponible
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def price_usd(self) -> Optional[float]:
        """Precio normalizado a USD si la moneda es USD."""
        if self.price and (self.currency or "").upper() == "USD":
            return self.price
        return None


@dataclass
class ScoreResult:
    """Resultado de evaluar una Listing con el LLM + reglas de negocio."""
    passed: bool
    score: float
    breakdown: dict[str, float]
    failed: list[str]                    # razones por las que NO pasó (si passed=False)
    # campos normalizados por el LLM / reglas
    neighbourhood: Optional[str] = None  # display canónico
    property_type: Optional[str] = None
    surface_m2: Optional[int] = None
    price_usd: Optional[float] = None
    outdoor_types: list[str] = field(default_factory=list)
    outdoor_best: Optional[str] = None
    near_avenue: bool = False
    near_subte: bool = False
    near_train: bool = False
    proximity_reason: Optional[str] = None
    summary: str = ""   # resumen de ventajas/desventajas: "+jardín +tren -escalera"
