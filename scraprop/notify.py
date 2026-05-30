"""Notificaciones por Telegram: alerta por propiedad + digest diario top-5."""
from __future__ import annotations

from typing import Optional

import requests

from .config import Settings
from .models import Listing, ScoreResult

# emoji por tipo de espacio exterior
_OUTDOOR_EMOJI = {"jardin": "🌳", "terraza": "🌅", "balcon": "🪟", "patio": "🌿"}
# medalla según puntos de barrio
_BARRIO_MEDAL = {3.0: "🥇", 2.0: "🥈", 1.0: "🥉"}
_STATUS_BADGE = {"pausada": "⏸️ PAUSADA", "finalizada": "🔴 FINALIZADA",
                 "no disponible": "⚠️ NO DISPONIBLE"}


def deeplink(listing_id: str) -> str:
    """Deep link a la app de ML (abre la publicación directo): meli://item?id=MLA123."""
    digits = "".join(c for c in listing_id if c.isdigit())
    return f"meli://item?id=MLA{digits}"


def _money(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def _pts(breakdown: dict, prefix: str):
    return next((v for k, v in breakdown.items() if k.startswith(prefix)), None)


def format_message(listing: Listing, r: ScoreResult) -> str:
    """Alerta en bullets: encabezado + datos en negrita + ventajas/desventajas con viñetas."""
    bp, op, pp = _pts(r.breakdown, "Barrio"), _pts(r.breakdown, "Exterior"), _pts(r.breakdown, "Precio")
    badge = f"  {_STATUS_BADGE[listing.status]}" if listing.status in _STATUS_BADGE else ""

    lines = [f"🏡 <b>{r.neighbourhood or 'Propiedad'}</b> · ⭐ <b>{r.score:g}</b>{badge}"]
    if listing.title:
        t = listing.title if len(listing.title) <= 75 else listing.title[:72] + "…"
        lines.append(f"<i>{t}</i>")

    data = []
    if r.price_usd:
        data.append(f"💰 <b>USD {_money(r.price_usd)}</b>")
    if r.surface_m2:
        data.append(f"📐 <b>{r.surface_m2} m²</b>")
    if listing.rooms:
        data.append(f"🛏 {listing.rooms}")
    if data:
        lines.append(" · ".join(data))

    # bullets de ventajas/desventajas
    if bp:
        lines.append(f"• {_BARRIO_MEDAL.get(bp, '📍')} <b>{r.neighbourhood}</b> +{bp:g}")
    if op and r.outdoor_best:
        e = _OUTDOOR_EMOJI.get(r.outdoor_best.lower(), "🌿")
        lines.append(f"• {e} <b>{r.outdoor_best}</b> +{op:g}")
    if pp:
        lines.append(f"• 💵 precio en banda +{pp:g}")
    prox = [n for n, on in (("avenida", r.near_avenue), ("subte", r.near_subte),
                            ("tren", r.near_train)) if on]
    if prox:
        lines.append(f"• 🚆 a ≤4 cuadras de {', '.join(prox)}")
    for con in [p for p in r.summary.split() if p.startswith("-")]:
        lines.append(f"• ⚠️ {con[1:]}")

    lines.append(f'📱 <a href="{deeplink(listing.listing_id)}">app</a> · '
                 f'🌐 <a href="{listing.url}">web</a>')
    return "\n".join(lines)


def alert_buttons(listing: Listing) -> list:
    """Botón inline (web) para la alerta. meli:// no se puede en botón (Telegram lo rechaza)."""
    return [[("🔗 Ver publicación", listing.url)]]


def format_top5(rows: list[dict]) -> str:
    """Tabla monoespaciada (Telegram <pre>) + links numerados, para el digest diario."""
    title = "🏆 <b>TOP 5 — mejores puntuadas</b>\n"
    if not rows:
        return title + "\n(sin propiedades que cumplan los filtros todavía)"

    header = "⭐  Barrio       USD   m²  Resumen"
    table = [header, "─" * len(header)]
    for row in rows:
        score = f"{row.get('score') or 0:g}".ljust(3)
        nb = (row.get("neighbourhood") or "?")[:11].ljust(11)
        price = row.get("price_usd")
        price_s = (f"{price/1000:.0f}k" if price else "?").ljust(4)
        surf = str(row.get("surface_m2") or "?").ljust(3)
        summ = row.get("summary") or ""
        table.append(f"{score} {nb} {price_s} {surf} {summ}")
    pre = "<pre>" + "\n".join(table) + "</pre>"

    links = []
    for row in rows:
        st = row.get("status")
        badge = f" {_STATUS_BADGE[st]}" if st in _STATUS_BADGE else ""
        app = deeplink(row.get("listing_id", ""))
        links.append(f'<b>{row.get("neighbourhood") or "ver"}</b> ⭐{row.get("score") or 0:g}: '
                     f'<a href="{app}">📱</a> · <a href="{row.get("url")}">🌐</a>{badge}')
    return f"{title}\n\n{pre}\n\n" + "\n".join(links)


def top5_buttons(rows: list[dict]) -> list:
    """Un botón inline (web) por propiedad del top-5."""
    return [[(f"{i}. {r.get('neighbourhood') or 'ver'} ⭐{r.get('score') or 0:g}", r.get("url"))]
            for i, r in enumerate(rows, 1)]


def _post(settings: Settings, method: str, payload: dict) -> bool:
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_id}/{method}",
            data=payload, timeout=20,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"  ❌ Error Telegram: {e}")
        return False


def _markup(buttons: Optional[list]) -> dict:
    if not buttons:
        return {}
    kb = [[{"text": t, "url": u} for (t, u) in row] for row in buttons]
    return {"reply_markup": __import__("json").dumps({"inline_keyboard": kb})}


def send(settings: Settings, message: str, photo: Optional[str] = None,
         buttons: Optional[list] = None, preview_url: Optional[str] = None) -> bool:
    """Si preview_url está seteado, Telegram muestra la tarjeta (foto/título) de esa URL."""
    if not settings.telegram_bot_id or not settings.telegram_id:
        print("  ⚠️  Telegram no configurado (TELEGRAM_BOT_ID/TELEGRAM_ID) — no se envía")
        return False
    markup = _markup(buttons)
    if photo:
        if _post(settings, "sendPhoto", {
            "chat_id": settings.telegram_id, "photo": photo,
            "caption": message, "parse_mode": "HTML", **markup,
        }):
            return True  # si falla la foto, cae a texto
    payload = {
        "chat_id": settings.telegram_id, "text": message,
        "parse_mode": "HTML", **markup,
    }
    if preview_url:
        payload["link_preview_options"] = __import__("json").dumps(
            {"url": preview_url, "prefer_large_media": True, "show_above_text": True}
        )
    else:
        payload["disable_web_page_preview"] = "true"
    return _post(settings, "sendMessage", payload)
