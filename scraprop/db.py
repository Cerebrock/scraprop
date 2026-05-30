"""Persistencia en SQLite: dedup (seen) + histórico de propiedades."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    listing_id    TEXT PRIMARY KEY,
    source        TEXT,
    url           TEXT,
    signature     TEXT,
    title         TEXT,
    neighbourhood TEXT,
    property_type TEXT,
    price_usd     REAL,
    surface_m2    INTEGER,
    rooms         INTEGER,
    outdoor       TEXT,
    score         REAL,
    passed        INTEGER,
    breakdown     TEXT,
    summary       TEXT,
    status        TEXT,
    tracked       INTEGER DEFAULT 0,
    notified      INTEGER DEFAULT 0,
    first_seen    TEXT,
    raw           TEXT
);
CREATE INDEX IF NOT EXISTS idx_signature ON properties(signature);
"""


class DB:
    def __init__(self, path: Path = config.DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # --- lecturas de dedup --- #
    def has_id(self, listing_id: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM properties WHERE listing_id = ?", (listing_id,)
        )
        return cur.fetchone() is not None

    def has_signature(self, signature: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM properties WHERE signature = ?", (signature,)
        )
        return cur.fetchone() is not None

    # --- escritura --- #
    def upsert(self, record: dict) -> None:
        record = dict(record)
        record.setdefault("first_seen", datetime.now().isoformat(timespec="seconds"))
        for k in ("breakdown", "raw"):
            if isinstance(record.get(k), (dict, list)):
                record[k] = json.dumps(record[k], ensure_ascii=False)
        cols = (
            "listing_id", "source", "url", "signature", "title", "neighbourhood",
            "property_type", "price_usd", "surface_m2", "rooms", "outdoor", "score",
            "passed", "breakdown", "summary", "status", "tracked", "notified",
            "first_seen", "raw",
        )
        values = [record.get(c) for c in cols]
        placeholders = ",".join("?" for _ in cols)
        self.conn.execute(
            f"INSERT OR REPLACE INTO properties ({','.join(cols)}) VALUES ({placeholders})",
            values,
        )
        self.conn.commit()

    def top(self, n: int = 5, only_passed: bool = True) -> list[dict]:
        """Mejores propiedades por score, excluyendo finalizadas/no disponibles."""
        where = "WHERE (status IS NULL OR status NOT IN ('finalizada','no disponible'))"
        if only_passed:
            where += " AND passed = 1"
        cur = self.conn.execute(
            f"SELECT listing_id, url, neighbourhood, price_usd, surface_m2, score, summary, status "
            f"FROM properties {where} ORDER BY score DESC, price_usd ASC LIMIT ?", (n,)
        )
        return [dict(r) for r in cur.fetchall()]

    def count_real(self) -> int:
        """Cantidad de propiedades reales scrapeadas (excluye migradas de seen.txt)."""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM properties WHERE source != 'legacy'"
        )
        return cur.fetchone()[0]

    def import_seen_txt(self, path: Path) -> int:
        """Migra urls del viejo outputs/seen.txt para no re-notificar publicaciones viejas."""
        from .dedup import listing_id_from_url

        if not path.exists():
            return 0
        n = 0
        for line in path.read_text().splitlines():
            lid = listing_id_from_url(line.strip())
            if lid and not self.has_id(lid):
                self.conn.execute(
                    "INSERT OR IGNORE INTO properties (listing_id, source, url, first_seen) "
                    "VALUES (?, 'legacy', ?, ?)",
                    (lid, line.strip(), datetime.now().isoformat(timespec="seconds")),
                )
                n += 1
        self.conn.commit()
        return n

    def close(self) -> None:
        self.conn.close()
