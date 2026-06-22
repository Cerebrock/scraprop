"""Configuración central: settings de entorno, reglas de negocio y URLs de búsqueda.

Todas las reglas de COMPRA (filtros duros + scoring) viven acá para que sean fáciles
de ajustar sin tocar la lógica del pipeline.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Rutas del proyecto
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "scraprop.db"
CSV_PATH = DATA_DIR / "scraped.csv"
STORAGE_STATE = DATA_DIR / "storage_state.json"
# Archivos privados (gitignored) con su ejemplo público (committed).
# Las URLs de búsqueda (con tu polígono) y el prompt del LLM son personales → no se commitean.
SEARCHES_FILE = ROOT / "searches.txt"
SEARCHES_EXAMPLE = ROOT / "searches.example.txt"
PROMPT_FILE = ROOT / "prompt.txt"
PROMPT_EXAMPLE = ROOT / "prompt.example.txt"


def load_search_urls() -> Optional[list[str]]:
    """Lee searches.txt (privado) si existe; si no, searches.example.txt."""
    for fp in (SEARCHES_FILE, SEARCHES_EXAMPLE):
        if fp.exists():
            urls = [ln.strip() for ln in fp.read_text().splitlines()
                    if ln.strip() and not ln.strip().startswith("#")]
            if urls:
                return urls
    return None


def load_prompt() -> Optional[str]:
    """Lee prompt.txt (privado) si existe; si no, prompt.example.txt."""
    for fp in (PROMPT_FILE, PROMPT_EXAMPLE):
        if fp.exists():
            return fp.read_text()
    return None


# --------------------------------------------------------------------------- #
# Settings de entorno
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    telegram_bot_id: Optional[str]
    telegram_id: Optional[str]
    gemini_api_key: Optional[str]
    gemini_model: str
    usd_ars: Optional[float]

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        usd_ars = os.getenv("USD_ARS")
        return cls(
            telegram_bot_id=os.getenv("TELEGRAM_BOT_ID") or None,
            telegram_id=os.getenv("TELEGRAM_ID") or None,
            gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
            gemini_model=os.getenv("GEMINI_MODEL") or "gemini-flash-lite-latest",
            usd_ars=float(usd_ars) if usd_ars else None,
        )


# --------------------------------------------------------------------------- #
# Reglas de negocio — COMPRA
# --------------------------------------------------------------------------- #
# Precio (USD)
PRICE_MIN_USD = 95_000
PRICE_MAX_USD = 200_000
# Bandas (min_inclusive, max_exclusive, puntos)
PRICE_BANDS = [
    (95_000, 120_000, 1.0),
    (120_000, 150_000, 2.0),
    (150_000, 200_001, 0.5),  # 200k inclusive
]

# Superficie total mínima (m²)
SURFACE_MIN_M2 = 90

# Antigüedad máxima de la publicación (días). Más viejo => no es gran oportunidad.
MAX_AGE_DAYS = 30

# Espacio exterior — al menos uno (filtro duro). Puntos: se toma el máximo presente.
OUTDOOR_POINTS = {
    "jardin": 3.0,
    "terraza": 2.0,
    "balcon": 1.0,
    "patio": 1.0,
}

# Tipos de propiedad permitidos (filtro duro). El resto (local, cochera, terreno,
# oficina, depósito, galpón...) se descarta.
ALLOWED_PROPERTY_TYPES = {"departamento", "ph", "casa", "loft", "duplex"}


@dataclass(frozen=True)
class Neighbourhood:
    key: str            # canónico para matching/scoring
    display: str        # nombre lindo para Telegram
    points: float       # puntos de scoring
    location_path: str  # segmento de path en la URL de búsqueda de ML
    aliases: tuple[str, ...] = ()  # variantes textuales para reconocerlo


# location_path:
#   CABA            -> "capital-federal/<slug>"
#   GBA Norte (VL)  -> "bsas-gba-norte/vicente-lopez/<slug>"
NEIGHBOURHOODS: list[Neighbourhood] = [
    Neighbourhood("chacarita", "Chacarita", 1.0, "capital-federal/chacarita"),
    Neighbourhood("coghlan", "Coghlan", 1.0, "capital-federal/coghlan"),
    Neighbourhood("palermo", "Palermo", 1.0, "capital-federal/palermo",
                  ("palermo hollywood", "palermo soho", "palermo chico", "las cañitas")),
    Neighbourhood("belgrano", "Belgrano", 3.0, "capital-federal/belgrano",
                  ("belgrano c", "belgrano r", "belgrano chico", "barrio chino")),
    Neighbourhood("saavedra", "Saavedra", 3.0, "capital-federal/saavedra"),
    Neighbourhood("nunez", "Núñez", 3.0, "capital-federal/nunez", ("núñez",)),
    Neighbourhood("florida este", "Florida Este", 2.0,
                  "bsas-gba-norte/vicente-lopez/florida", ("florida", "florida este")),
    Neighbourhood("vicente lopez", "Vicente López", 2.0,
                  "bsas-gba-norte/vicente-lopez/vicente-lopez",
                  ("vicente lópez", "vte lopez", "vte. lopez")),
    Neighbourhood("colegiales", "Colegiales", 2.0, "capital-federal/colegiales"),
    Neighbourhood("villa urquiza", "Villa Urquiza", 2.0,
                  "capital-federal/villa-urquiza", ("v. urquiza",)),
]

# Tipos de inmueble a recorrer en la búsqueda de ML
ML_PROPERTY_TYPES = ["departamentos", "ph", "casas"]

# Excluir emprendimientos / pozo / proyectos (no son una unidad concreta a comprar)
ML_EXCLUDE_EMPRENDIMIENTOS = True

# Patrón para reconocer emprendimientos / pozo / proyectos en CUALQUIER texto (card o
# detalle). Se descartan SIEMPRE: si la publicación "dice emprendimiento" (o es pozo / en
# construcción / pre-venta / "desde U$S" / "unidades de…"), no es una unidad concreta a
# comprar y va afuera. Es la SSOT de la regla; la usan la card de búsqueda y el detalle.
EMPRENDIMIENTO_RE = re.compile(
    r"emprendimiento|edificio en |en pozo|\ben pozo\b|en construcc|"
    r"pre[\s-]?venta|preventa|desde\s*(?:u\$s|usd|\$)|unidades?\s+de\b|"
    r"pozo\b|fideicomiso|proyecto inmobiliario",
    re.IGNORECASE,
)
# Señal por slug de la URL de ML: los emprendimientos casi siempre tienen el descriptor
# arrancando en "edificio-…"/"imponente-edificio"/"torre-…"/"venta-unidades-de" (en vez de
# "departamento-…"/"ph-…"/"casa-…"), aunque el título sea branded (BOLD, ICONIQ, etc.).
# Anclado al id MLA para no marcar de más un slug que mencione "edificio" al pasar.
_EMPRENDIMIENTO_URL_RE = re.compile(
    r"/MLA-\d+-(?:imponente-|importante-|gran-)?(?:edificio|torre)\b"
    r"|/MLA-\d+-venta-unidades-de\b",
    re.IGNORECASE,
)


def is_emprendimiento(*texts: Optional[str]) -> bool:
    """True si algún texto (título/descr/barrio/URL) delata un emprendimiento/pozo/proyecto."""
    blob = " ".join(t for t in texts if t)
    return bool(EMPRENDIMIENTO_RE.search(blob) or _EMPRENDIMIENTO_URL_RE.search(blob))

# Si las búsquedas usan polígono dibujado a mano, el polígono define la zona: NO se descarta
# por "barrio fuera de zona" (el barrio solo suma puntos). Poné True para filtro estricto.
BARRIO_HARD_FILTER = False


def match_neighbourhood(text: Optional[str]) -> Optional[Neighbourhood]:
    """Devuelve el barrio canónico que mejor matchea un texto (o None)."""
    if not text:
        return None
    t = text.strip().lower()
    # match exacto por key/alias primero
    for n in NEIGHBOURHOODS:
        if t == n.key or t in n.aliases:
            return n
    # match por substring (ej: "Palermo Hollywood, Capital Federal")
    for n in NEIGHBOURHOODS:
        needles = (n.key,) + n.aliases
        if any(needle in t for needle in needles):
            return n
    return None


def price_points(price_usd: Optional[float]) -> float:
    if not price_usd:
        return 0.0
    for lo, hi, pts in PRICE_BANDS:
        if lo <= price_usd < hi:
            return pts
    return 0.0


# Puntaje máximo posible (mejor barrio + mejor exterior + mejor banda de precio), para
# normalizar el score a /10.
MAX_SCORE = (max(n.points for n in NEIGHBOURHOODS)
             + max(OUTDOOR_POINTS.values())
             + max(p for _, _, p in PRICE_BANDS))


def normalize_score(raw: float) -> float:
    """Escala el puntaje crudo a /10."""
    return round(raw / MAX_SCORE * 10, 1) if MAX_SCORE else round(raw, 1)


def outdoor_points(outdoor_types: list[str]) -> tuple[float, Optional[str]]:
    """Puntos del mejor espacio exterior presente y su tipo."""
    best_pts, best_type = 0.0, None
    for t in outdoor_types or []:
        pts = OUTDOOR_POINTS.get(t.strip().lower(), 0.0)
        if pts > best_pts:
            best_pts, best_type = pts, t.strip().lower()
    return best_pts, best_type
