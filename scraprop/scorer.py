"""Scorer: extrae campos blandos con Gemini, aplica filtros duros y calcula el puntaje.

El LLM se usa solo para lo que requiere criterio (espacio exterior, cercanía a avenida/
subte/tren, barrio canónico, tipo de propiedad). Los filtros duros y el scoring se calculan
en Python de forma determinística. Si no hay API key o el LLM falla, hay un fallback por
heurística de keywords para que el pipeline siga funcionando (degradado).
"""
from __future__ import annotations

import json
import re
from typing import Optional

from . import config
from .models import Listing, ScoreResult

_OUTDOOR_KEYWORDS = {
    "jardin": ("jardín", "jardin"),
    "terraza": ("terraza", "terraza propia", "roof"),
    "balcon": ("balcón", "balcon", "balcón aterrazado"),
    "patio": ("patio",),
}
_AVENUE_KW = ("avenida", "av.", "av ", "cabildo", "libertador", "maipú", "santa fe", "corrientes")
_SUBTE_KW = ("subte", "línea b", "linea b", "línea d", "linea d", "estación de subte")
_TRAIN_KW = ("tren", "estación", "estacion", "ferrocarril", "mitre", "belgrano norte")
_TYPE_KW = {
    "ph": ("ph",),
    "casa": ("casa", "chalet"),
    "departamento": ("departamento", "depto", "monoambiente", "loft", "semipiso", "piso"),
    "local": ("local", "fondo de comercio"),
    "cochera": ("cochera", "garage"),
    "terreno": ("terreno", "lote"),
    "oficina": ("oficina",),
    "deposito": ("depósito", "deposito", "galpón", "galpon"),
}

# El prompt se carga desde prompt.txt (privado) o prompt.example.txt (ver config.load_prompt).
# Fallback mínimo por si faltan ambos archivos.
_PROMPT_FALLBACK = (
    "Analizá la publicación y devolvé SOLO un JSON con las claves: property_type, "
    "neighbourhood, surface_m2_total, outdoor_spaces (lista de balcon/terraza/jardin/patio), "
    "near_avenue, near_subte, near_train (booleanos). "
    "Datos: {title} | {location} | {price} | {surface} | {description}"
)


class Scorer:
    def __init__(self, settings: Optional[config.Settings] = None):
        self.settings = settings or config.Settings.load()
        self.prompt = config.load_prompt() or _PROMPT_FALLBACK
        self._client = None
        if self.settings.gemini_api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.settings.gemini_api_key)
                print(f"  🤖 Gemini listo (model={self.settings.gemini_model})")
            except Exception as e:
                print(f"  ⚠️  No se pudo inicializar Gemini: {e} — uso heurística")
        else:
            print("  ⚠️  Sin GEMINI_API_KEY — uso heurística por keywords")

    # ------------------------------------------------------------------ #
    def evaluate(self, listing: Listing) -> ScoreResult:
        extracted = self._extract(listing)
        return self._apply_rules(listing, extracted)

    # --- extracción (LLM o heurística) --- #
    def _extract(self, listing: Listing) -> dict:
        if self._client:
            data = self._extract_llm(listing)
            if data is not None:
                return data
        return self._extract_heuristic(listing)

    def _extract_llm(self, listing: Listing) -> Optional[dict]:
        prompt = self.prompt.format(
            title=listing.title or "",
            location=listing.neighbourhood_raw or listing.address or "",
            price=f"{listing.price} {listing.currency}" if listing.price else "",
            surface=f"{listing.surface_m2} m²" if listing.surface_m2 else "",
            description=(listing.description or "")[:4000],
        )
        try:
            from google.genai import types
            resp = self._client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
            text = (resp.text or "").strip()
            # por las dudas, recortar a las llaves del JSON
            m = re.search(r"\{.*\}", text, re.DOTALL)
            return json.loads(m.group() if m else text)
        except Exception as e:
            print(f"  ⚠️  Falla LLM ({e}) — heurística para {listing.listing_id}")
            return None

    def _extract_heuristic(self, listing: Listing) -> dict:
        text = " ".join(
            x for x in [listing.title, listing.neighbourhood_raw, listing.address,
                        listing.description, listing.url] if x
        ).lower()

        outdoor = [k for k, kws in _OUTDOOR_KEYWORDS.items() if any(w in text for w in kws)]
        ptype = "otro"
        for t, kws in _TYPE_KW.items():
            if any(w in text for w in kws):
                ptype = t
                break
        nb = config.match_neighbourhood(listing.neighbourhood_raw) \
            or config.match_neighbourhood(listing.address) \
            or config.match_neighbourhood(text)
        return {
            "property_type": ptype,
            "neighbourhood": nb.key if nb else "otro",
            "surface_m2_total": listing.surface_m2,
            "outdoor_spaces": outdoor,
            "near_avenue": any(w in text for w in _AVENUE_KW),
            "near_subte": any(w in text for w in _SUBTE_KW),
            "near_train": any(w in text for w in _TRAIN_KW),
            "proximity_reason": "heurística por keywords",
        }

    # --- reglas duras + scoring --- #
    def _apply_rules(self, listing: Listing, ext: dict) -> ScoreResult:
        failed: list[str] = []

        # precio en USD
        price_usd = listing.price_usd
        if price_usd is None and listing.price and (listing.currency or "").upper() == "ARS" \
                and self.settings.usd_ars:
            price_usd = listing.price / self.settings.usd_ars

        # superficie
        surface = listing.surface_m2 or ext.get("surface_m2_total")
        try:
            surface = int(surface) if surface else None
        except (TypeError, ValueError):
            surface = None

        # barrio
        nb = config.match_neighbourhood(ext.get("neighbourhood")) \
            or config.match_neighbourhood(listing.neighbourhood_raw) \
            or config.match_neighbourhood(listing.address)

        outdoor_types = [t for t in (ext.get("outdoor_spaces") or [])
                         if t.strip().lower() in config.OUTDOOR_POINTS]
        out_pts, out_best = config.outdoor_points(outdoor_types)

        near_av = bool(ext.get("near_avenue"))
        near_su = bool(ext.get("near_subte"))
        near_tr = bool(ext.get("near_train"))
        ptype = (ext.get("property_type") or "otro").lower()

        # ----- filtros duros ----- #
        if ptype not in config.ALLOWED_PROPERTY_TYPES:
            failed.append(f"tipo no habitacional ({ptype})")
        if config.BARRIO_HARD_FILTER and nb is None:
            failed.append("barrio fuera de zona")
        if not outdoor_types:
            failed.append("sin espacio exterior")
        if not (near_av or near_su or near_tr):
            failed.append("lejos de avenida/subte/tren")
        if surface is None or surface < config.SURFACE_MIN_M2:
            failed.append(f"superficie {surface or '?'} < {config.SURFACE_MIN_M2} m²")
        if price_usd is None:
            failed.append("precio USD desconocido")
        elif not (config.PRICE_MIN_USD <= price_usd <= config.PRICE_MAX_USD):
            failed.append(f"precio USD {price_usd:,.0f} fuera de rango")
        # antigüedad: solo descarta si la conocemos y supera el máximo
        if listing.posted_days_ago is not None and listing.posted_days_ago > config.MAX_AGE_DAYS:
            failed.append(f"publicado hace {listing.posted_days_ago}d (> {config.MAX_AGE_DAYS})")

        passed = not failed

        # ----- scoring ----- #
        # Se calcula con los componentes conocidos aunque NO pase los filtros duros (útil para
        # rankear las propiedades marcadas a mano). `passed` queda como gate aparte para notificar.
        breakdown: dict[str, float] = {}
        if nb:
            breakdown[f"Barrio ({nb.display})"] = nb.points
        if out_pts:
            breakdown[f"Exterior ({out_best})"] = out_pts
        pp = config.price_points(price_usd)
        if pp:
            breakdown[f"Precio (USD {price_usd:,.0f})"] = pp
        score = config.normalize_score(sum(breakdown.values()))  # /10

        # ----- resumen de ventajas/desventajas ----- #
        summary_parts = [f"+{t}" for t in outdoor_types]
        for label, on in (("+tren", near_tr), ("+subte", near_su), ("+av", near_av)):
            if on:
                summary_parts.append(label)
        desc = (listing.description or "").lower()
        cons = [
            ("-escalera", ("escalera", "planta alta", "por escalera")),
            ("-sin ascensor", ("sin ascensor",)),
            ("-reciclar", ("a reciclar", "reciclar", "refaccion", "a refaccionar")),
        ]
        for tag, kws in cons:
            if any(k in desc for k in kws):
                summary_parts.append(tag)
        summary = " ".join(summary_parts)

        # display del barrio: el canónico si matchea; si no, el del raw (ej "Villa Crespo")
        if nb:
            display_nb = nb.display
        else:
            raw = listing.neighbourhood_raw or listing.address or ""
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            display_nb = parts[1] if len(parts) >= 2 else (
                parts[0] if parts else (ext.get("neighbourhood") or None))

        return ScoreResult(
            passed=passed,
            score=score,
            breakdown=breakdown,
            failed=failed,
            neighbourhood=display_nb,
            property_type=ptype,
            surface_m2=surface,
            price_usd=price_usd,
            outdoor_types=outdoor_types,
            outdoor_best=out_best,
            near_avenue=near_av,
            near_subte=near_su,
            near_train=near_tr,
            proximity_reason=ext.get("proximity_reason"),
            summary=summary,
        )
