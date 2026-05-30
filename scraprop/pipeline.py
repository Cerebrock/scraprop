"""Orquestación de una pasada: search → prefiltro → detalle → LLM → filtros → notificar/guardar."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config, notify
from .db import DB
from .dedup import content_signature
from .fetch import BrowserSession
from .models import Listing, ScoreResult
from .scorer import Scorer
from .sources import SOURCES

_CSV_COLS = [
    "first_seen", "listing_id", "status", "tracked", "passed", "score", "neighbourhood",
    "property_type", "price_usd", "surface_m2", "rooms", "outdoor", "summary",
    "near_avenue", "near_subte", "near_train", "posted_days_ago", "url", "breakdown", "failed",
]


def _cheap_prefilter(listing: Listing) -> Optional[str]:
    """Descarta sin LLM cuando hay datos confiables de la card. Devuelve motivo o None."""
    if listing.price_usd is not None and not (
        config.PRICE_MIN_USD <= listing.price_usd <= config.PRICE_MAX_USD
    ):
        return f"precio USD {listing.price_usd:,.0f} fuera de rango"
    if listing.surface_m2 is not None and listing.surface_m2 < config.SURFACE_MIN_M2:
        return f"superficie {listing.surface_m2} < {config.SURFACE_MIN_M2}"
    return None


def _append_csv(record: dict) -> None:
    config.CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not config.CSV_PATH.exists()
    with config.CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(record)


def run(dry_run: bool = False, limit: Optional[int] = None,
        notify_first_run: bool = False, force_backfill: bool = False) -> None:
    print("\n" + "=" * 80)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] SCRAPROP — pasada {'(DRY-RUN)' if dry_run else ''}")
    print("=" * 80)

    settings = config.Settings.load()
    db = DB()
    migrated = db.import_seen_txt(config.ROOT / "outputs" / "seen.txt")
    if migrated:
        print(f"  📁 Migradas {migrated} URLs viejas de seen.txt a SQLite")

    # ML oculta la fecha de publicación, así que aproximamos "freshness" con un backfill:
    # la primera corrida carga el inventario actual SIN notificar; después solo se notifican
    # las propiedades nuevas (que por aparecer recién, son recientes).
    backfill = (force_backfill or db.count_real() == 0) and not notify_first_run and not dry_run
    if backfill:
        print("  📦 Backfill silencioso (se cargan como vistas, sin notificar).")

    scorer = Scorer(settings)

    # 1) recolectar candidatas (páginas de búsqueda)
    candidates: list[tuple] = []  # (source, listing)
    seen_ids: set[str] = set()
    with BrowserSession() as session:
        for source in SOURCES:
            for url in source.search_urls():
                print(f"\n[{datetime.now():%H:%M:%S}] 🔎 {url}")
                html = session.get(url, wait_selector=source.search_wait_selector)
                if not html:
                    continue
                listings = source.parse_search(html, url)
                print(f"  → {len(listings)} cards")
                for listing in listings:
                    if listing.listing_id in seen_ids or db.has_id(listing.listing_id):
                        continue
                    reason = _cheap_prefilter(listing)
                    if reason:
                        continue
                    seen_ids.add(listing.listing_id)
                    candidates.append((source, listing))

        print(f"\n[{datetime.now():%H:%M:%S}] 🆕 {len(candidates)} candidatas nuevas")
        if limit:
            candidates = candidates[:limit]
            print(f"  🔬 Limitado a {len(candidates)}")

        # 2) detalle + LLM + reglas
        notified = 0
        for i, (source, listing) in enumerate(candidates, 1):
            print(f"\n[{i}/{len(candidates)}] {listing.url}")
            detail_html = session.get(listing.url, wait_selector=source.detail_wait_selector,
                                       scroll=True)
            if detail_html:
                listing = source.parse_detail(detail_html, listing)

            result = scorer.evaluate(listing)
            signature = content_signature(
                result.neighbourhood, result.price_usd, result.surface_m2, listing.rooms
            )

            dup = db.has_signature(signature)
            status = "✅ PASA" if result.passed else "✋ descartada"
            if dup:
                status += " (repost duplicado)"
            print(f"  {status} score={result.score} "
                  f"{'| ' + ', '.join(result.failed) if result.failed else ''}")

            record = _build_record(listing, result, signature, notified=False)
            if dry_run:
                continue

            should_notify = result.passed and not dup and not backfill
            if should_notify:
                msg = notify.format_message(listing, result)
                ok = notify.send(settings, msg, buttons=notify.alert_buttons(listing),
                                 preview_url=listing.url)
                if ok:
                    notified += 1
                    record["notified"] = 1
                    print("  📨 Notificado por Telegram")
            db.upsert(record)
            _append_csv(_flat_record(listing, result, signature))

    print(f"\n[{datetime.now():%H:%M:%S}] ✅ Fin. {notified} notificadas.")
    db.close()


def digest(n: int = 5, only_passed: bool = True) -> None:
    """Manda por Telegram el top-N de mejores propiedades (para correr 1 vez/día)."""
    settings = config.Settings.load()
    db = DB()
    rows = db.top(n, only_passed=only_passed)
    # si no hay ninguna que pase los filtros, mostrar las mejores igual
    if not rows and only_passed:
        rows = db.top(n, only_passed=False)
    db.close()
    msg = notify.format_top5(rows)
    print(f"[{datetime.now():%H:%M:%S}] 📊 Digest top-{n}: {len(rows)} propiedades")
    notify.send(settings, msg, buttons=notify.top5_buttons(rows))


def ingest_html(path: str) -> None:
    """Ingiere una página de Favoritos de ML guardada (offline, sin tocar la red).

    Extrae datos + status (activa/pausada/finalizada) de cada card, las puntúa y guarda
    como marcadas (tracked=1).
    """
    from pathlib import Path as _Path
    from .sources.mercadolibre import MercadoLibre

    p = _Path(path).expanduser()
    if not p.exists():
        print(f"  ❌ No existe el archivo: {p}")
        return
    ml = MercadoLibre()
    listings = ml.parse_wishlist(p.read_text())
    print(f"[{datetime.now():%H:%M:%S}] 📌 {len(listings)} favoritos en {p.name}")

    settings = config.Settings.load()
    db = DB()
    scorer = Scorer(settings)
    by_status: dict[str, int] = {}
    for listing in listings:
        result = scorer.evaluate(listing)
        signature = content_signature(
            result.neighbourhood, result.price_usd, result.surface_m2, listing.rooms
        )
        db.upsert(_build_record(listing, result, signature, notified=False, tracked=True))
        _append_csv(_flat_record(listing, result, signature, tracked=True))
        by_status[listing.status or "?"] = by_status.get(listing.status or "?", 0) + 1
        flag = "✅" if result.passed else "✋"
        print(f"  {listing.listing_id} | {listing.status or '?':10} | {flag} score={result.score} "
              f"| {result.neighbourhood or '?'} | {result.surface_m2 or '?'}m² "
              f"| ${result.price_usd or '?'} | {(listing.title or '')[:40]}")
    db.close()
    print(f"[{datetime.now():%H:%M:%S}] ✅ Ingesta completa: {dict(by_status)}")


def ingest(urls: list[str]) -> None:
    """Scrapea, parsea, puntúa y guarda una lista de URLs marcadas a mano (tracked=1).

    Se guardan SIEMPRE (cumplan o no los filtros) con su status (activa/pausada/finalizada).
    """
    from .dedup import listing_id_from_url
    from .sources.mercadolibre import MercadoLibre

    urls = [u.strip() for u in urls if u.strip() and not u.strip().startswith("#")]
    if not urls:
        print("  ⚠️  No hay URLs para ingerir.")
        return
    print(f"[{datetime.now():%H:%M:%S}] 📌 Ingiriendo {len(urls)} URLs marcadas")

    settings = config.Settings.load()
    db = DB()
    scorer = Scorer(settings)
    ml = MercadoLibre()
    with BrowserSession() as session:
        for i, url in enumerate(urls, 1):
            lid = listing_id_from_url(url)
            if not lid:
                print(f"  [{i}] ⚠️  No es una URL de MercadoLibre: {url}")
                continue
            listing = Listing(source=ml.name, listing_id=lid, url=url)
            html = session.get(url, wait_selector=ml.detail_wait_selector, scroll=True)
            if html:
                listing = ml.parse_detail(html, listing)
            result = scorer.evaluate(listing)
            signature = content_signature(
                result.neighbourhood, result.price_usd, result.surface_m2, listing.rooms
            )
            record = _build_record(listing, result, signature, notified=False, tracked=True)
            db.upsert(record)
            _append_csv(_flat_record(listing, result, signature, tracked=True))
            print(f"  [{i}] {lid} | status={listing.status or '?'} | "
                  f"{'✅' if result.passed else '✋'} score={result.score} | "
                  f"{result.neighbourhood or '?'} {result.surface_m2 or '?'}m² "
                  f"${result.price_usd or '?'}")
    db.close()
    print(f"[{datetime.now():%H:%M:%S}] ✅ Ingesta completa.")


def _build_record(listing: Listing, r: ScoreResult, signature: str, notified: bool,
                  tracked: bool = False) -> dict:
    return {
        "listing_id": listing.listing_id,
        "source": listing.source,
        "url": listing.url,
        "signature": signature,
        "title": listing.title,
        "neighbourhood": r.neighbourhood,
        "property_type": r.property_type,
        "price_usd": r.price_usd,
        "surface_m2": r.surface_m2,
        "rooms": listing.rooms,
        "outdoor": r.outdoor_best,
        "score": r.score,
        "passed": int(r.passed),
        "breakdown": r.breakdown,
        "summary": r.summary,
        "status": listing.status,
        "tracked": int(tracked),
        "notified": int(notified),
        "raw": {"failed": r.failed, "posted_days_ago": listing.posted_days_ago},
    }


def _flat_record(listing: Listing, r: ScoreResult, signature: str, tracked: bool = False) -> dict:
    return {
        "first_seen": datetime.now().isoformat(timespec="seconds"),
        "listing_id": listing.listing_id,
        "status": listing.status,
        "tracked": int(tracked),
        "passed": int(r.passed),
        "score": r.score,
        "neighbourhood": r.neighbourhood,
        "property_type": r.property_type,
        "price_usd": r.price_usd,
        "surface_m2": r.surface_m2,
        "rooms": listing.rooms,
        "outdoor": r.outdoor_best,
        "summary": r.summary,
        "near_avenue": int(r.near_avenue),
        "near_subte": int(r.near_subte),
        "near_train": int(r.near_train),
        "posted_days_ago": listing.posted_days_ago,
        "url": listing.url,
        "breakdown": "; ".join(f"{k}:{v:g}" for k, v in r.breakdown.items()),
        "failed": "; ".join(r.failed),
    }
