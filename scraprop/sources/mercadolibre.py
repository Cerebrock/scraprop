"""Adapter de MercadoLibre Inmuebles (venta).

El parsing es defensivo: si un campo no se puede extraer, queda en None y el prefiltro
lo deja pasar (fail-open) para que lo resuelva el detalle + LLM. Así un cambio de markup
no descarta propiedades válidas por error.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from .. import config
from ..dedup import listing_id_from_url
from ..models import Listing
from .base import SourceAdapter

_M2_RE = re.compile(r"(\d+)\s*m[²2]")
# Emprendimientos / pozo / proyectos (no son una unidad concreta a comprar) → excluir
_EMPRENDIMIENTO_RE = re.compile(
    r"edificio en |emprendimiento|en pozo|en construcc|desde\s*(?:u\$s|usd|\$)", re.IGNORECASE
)
_AMB_RE = re.compile(r"(\d+)\s*ambiente")
_DORM_RE = re.compile(r"(\d+)\s*(?:dormitorio|habitaci[oó]n)")
_NUM_RE = re.compile(r"[\d.]+")


def _to_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _NUM_RE.search(text.replace(".", ""))
    return int(m.group()) if m else None


class MercadoLibre(SourceAdapter):
    name = "mercadolibre"
    base = "https://listado.mercadolibre.com.ar/inmuebles"
    search_wait_selector = "div.ui-search-result, li.ui-search-layout__item, div.poly-card"
    detail_wait_selector = "h1.ui-pdp-title, .ui-pdp-container"

    # ------------------------------------------------------------------ #
    def search_urls(self) -> list[str]:
        # URLs fijas elegidas por el usuario (searches.txt) tienen prioridad.
        fixed = config.load_search_urls()
        if fixed:
            return fixed
        # Default generado: sin filtros en la URL (el token _PriceRange con barrio da
        # Zero-Results en ML). El filtrado de precio/superficie se hace en código.
        urls = []
        for tipo in config.ML_PROPERTY_TYPES:
            for n in config.NEIGHBOURHOODS:
                urls.append(f"{self.base}/{tipo}/venta/{n.location_path}/")
        return urls

    # ------------------------------------------------------------------ #
    def _card_to_listing(self, card) -> Optional[Listing]:
        """Extrae una Listing de una card (poly-card / ui-search-result)."""
        link = card.select_one('a[href*="MLA-"], a.poly-component__title, a.ui-search-link')
        if not link or not link.get("href"):
            return None
        url = link["href"].split("#")[0]
        lid = listing_id_from_url(url)
        if not lid:
            return None

        listing = Listing(source=self.name, listing_id=lid, url=url)
        listing.title = (link.get_text(strip=True) or None)

        # precio + moneda
        money = card.select_one(".andes-money-amount, .ui-search-price__second-line .price-tag")
        if money:
            sym = money.select_one(".andes-money-amount__currency-symbol, .price-tag-symbol")
            frac = money.select_one(".andes-money-amount__fraction, .price-tag-fraction")
            if frac:
                listing.price = float((_to_int(frac.get_text()) or 0))
            sym_txt = (sym.get_text(strip=True) if sym else "") or money.get_text()
            listing.currency = "USD" if "U$S" in sym_txt or "US" in sym_txt else "ARS"

        # atributos (m², ambientes)
        attrs_text = " ".join(
            el.get_text(" ", strip=True)
            for el in card.select(
                ".poly-attributes-list__item, .poly-component__attributes-list li, "
                ".ui-search-item__group__element, .ui-search-card-attributes__attribute"
            )
        ).lower()
        if attrs_text:
            tot = re.search(r"(\d+)\s*m[²2]\s*tot", attrs_text)
            m2 = tot or _M2_RE.search(attrs_text)
            if m2:
                listing.surface_m2 = int(m2.group(1))
            amb = _AMB_RE.search(attrs_text)
            if amb:
                listing.rooms = int(amb.group(1))

        # ubicación
        loc = card.select_one(
            ".poly-component__location, .ui-search-item__location, .ui-search-item__group--location"
        )
        if loc:
            listing.neighbourhood_raw = loc.get_text(" ", strip=True)

        img = card.select_one("img")
        if img:
            listing.image = img.get("data-src") or img.get("src")
        return listing

    def parse_search(self, html: str, search_url: str) -> list[Listing]:
        soup = BeautifulSoup(html, "lxml")
        listings: dict[str, Listing] = {}
        skipped_emp = 0

        cards = soup.select("li.ui-search-layout__item, div.ui-search-result, div.poly-card")
        for card in cards:
            listing = self._card_to_listing(card)
            if not listing or listing.listing_id in listings:
                continue
            if config.ML_EXCLUDE_EMPRENDIMIENTOS:
                card_text = f"{listing.title or ''} {card.get_text(' ', strip=True)}"
                if _EMPRENDIMIENTO_RE.search(card_text):
                    skipped_emp += 1
                    continue
            listings[listing.listing_id] = listing
        if skipped_emp:
            print(f"  ⊘ {skipped_emp} emprendimientos excluidos")

        # Fallback: si los selectores fallaron, juntar al menos los links de items
        if not listings:
            for a in soup.select('a[href*="/MLA-"]'):
                url = a["href"].split("#")[0]
                lid = listing_id_from_url(url)
                if lid and lid not in listings:
                    listings[lid] = Listing(source=self.name, listing_id=lid, url=url)

        return list(listings.values())

    def parse_wishlist(self, html: str) -> list[Listing]:
        """Parsea una página de Favoritos de ML guardada (offline), con status por card."""
        soup = BeautifulSoup(html, "lxml")
        out: dict[str, Listing] = {}
        for card in soup.select("div.poly-card, li.ui-search-layout__item, div.ui-search-result"):
            listing = self._card_to_listing(card)
            if not listing or listing.listing_id in out:
                continue
            txt = card.get_text(" ", strip=True).lower()
            if "finalizad" in txt:
                listing.status = "finalizada"
            elif "pausad" in txt:
                listing.status = "pausada"
            else:
                listing.status = "activa"
            # texto para el scorer (sin página de detalle)
            listing.description = " | ".join(
                x for x in [listing.title, listing.neighbourhood_raw] if x
            )
            out[listing.listing_id] = listing
        return list(out.values())

    # ------------------------------------------------------------------ #
    def parse_detail(self, html: str, listing: Listing) -> Listing:
        soup = BeautifulSoup(html, "lxml")

        # título
        h1 = soup.select_one("h1.ui-pdp-title")
        if h1:
            listing.title = h1.get_text(strip=True)

        # precio desde el bloque de precio del PDP
        money = soup.select_one(".ui-pdp-price__second-line .andes-money-amount, .ui-pdp-price .andes-money-amount")
        if money:
            frac = money.select_one(".andes-money-amount__fraction")
            sym = money.select_one(".andes-money-amount__currency-symbol")
            if frac:
                listing.price = float((_to_int(frac.get_text()) or 0))
            sym_txt = (sym.get_text(strip=True) if sym else "") or ""
            listing.currency = "USD" if "U$S" in sym_txt or "US" in sym_txt else (listing.currency or "ARS")

        # specs (tabla de características + highlighted)
        specs: dict[str, str] = {}
        for row in soup.select(".andes-table__row, .ui-pdp-specs__table tr"):
            th = row.select_one("th, .andes-table__header")
            td = row.select_one("td, .andes-table__column--value")
            if th and td:
                specs[th.get_text(strip=True).lower()] = td.get_text(strip=True)
        for hi in soup.select(".ui-pdp-highlighted-specs-res__icon-label, .ui-pdp-highlighted-specs-res__attribute-value"):
            txt = hi.get_text(" ", strip=True).lower()
            m2 = re.search(r"(\d+)\s*m[²2]", txt)
            if m2 and ("tot" in txt or not listing.surface_m2):
                listing.surface_m2 = int(m2.group(1))
            amb = _AMB_RE.search(txt)
            if amb:
                listing.rooms = int(amb.group(1))

        if not listing.surface_m2:
            for key in ("superficie total", "superficie", "superficie cubierta"):
                if key in specs:
                    listing.surface_m2 = _to_int(specs[key])
                    if listing.surface_m2:
                        break
        if not listing.rooms:
            for key in ("ambientes", "dormitorios"):
                if key in specs:
                    listing.rooms = _to_int(specs[key])
                    if listing.rooms:
                        break

        # ML no expone la fecha de publicación; la frescura se aproxima con el backfill.

        # Open Graph: datos limpios provistos por ML (título, descripción, imagen).
        def _og(prop):
            m = soup.find("meta", property=prop)
            return m.get("content") if m and m.get("content") else None
        og_title, og_desc, og_image = _og("og:title"), _og("og:description"), _og("og:image")
        if og_image:
            listing.image = og_image  # imagen confiable para el preview

        # Estado: SOLO banners específicos de ML (evitar falsos positivos de frases genéricas
        # como "no está disponible", que aparece en disclaimers de cualquier página).
        low = html.lower()
        if "publicación pausada" in low or "publicacion pausada" in low:
            listing.status = "pausada"
        elif "publicación finalizada" in low or "publicacion finalizada" in low:
            listing.status = "finalizada"
        else:
            listing.status = "activa"

        desc_el = soup.select_one(".ui-pdp-description__content")
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        # JSON-LD como respaldo de precio/dirección
        if not listing.price_usd:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string or "")
                except Exception:
                    continue
                items = data if isinstance(data, list) else [data]
                for d in items:
                    if not isinstance(d, dict):
                        continue
                    offers = d.get("offers") or {}
                    if not listing.price and offers.get("price"):
                        listing.price = float(offers["price"])
                        listing.currency = offers.get("priceCurrency", listing.currency)
                    addr = d.get("address")
                    if not listing.address and isinstance(addr, dict):
                        listing.address = addr.get("streetAddress") or addr.get("addressLocality")

        # Filosofía: extraer amplio (texto limpio: OG + card + specs + descripción) y dejar
        # que el LLM parsee barrio/exterior/cercanía. NO usamos selectores frágiles de barrio.
        spec_txt = " | ".join(f"{k}: {v}" for k, v in specs.items())
        listing.description = " | ".join(
            x for x in [og_title, listing.neighbourhood_raw, listing.address,
                        spec_txt, description, og_desc] if x
        )
        return listing
