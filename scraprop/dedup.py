"""Deduplicación: identidad exacta por id de publicación y firma de contenido (anti-repost)."""
from __future__ import annotations

import hashlib
import re
from typing import Optional

_MLA_RE = re.compile(r"(MLA)[-_]?(\d+)", re.IGNORECASE)


def listing_id_from_url(url: str) -> Optional[str]:
    """Extrae el id canónico de MercadoLibre desde una URL (ej 'MLA-1234567890')."""
    m = _MLA_RE.search(url or "")
    if not m:
        return None
    return f"MLA-{m.group(2)}"


def content_signature(
    neighbourhood: Optional[str],
    price_usd: Optional[float],
    surface_m2: Optional[int],
    rooms: Optional[int],
) -> str:
    """Firma estable para detectar la *misma* propiedad republicada con otro id.

    Agrupa precio en miles de USD para tolerar pequeñas variaciones.
    """
    nb = (neighbourhood or "").strip().lower()
    price_bucket = int(round((price_usd or 0) / 1000))
    raw = f"{nb}|{price_bucket}|{surface_m2 or 0}|{rooms or 0}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
