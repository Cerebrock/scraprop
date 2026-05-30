"""CLI: `python -m scraprop [run|login|add] [opciones]`."""
import argparse
from pathlib import Path

from . import config, pipeline
from .fetch import login


def main() -> None:
    p = argparse.ArgumentParser(prog="scraprop",
                                description="Monitor de compra de propiedades (MercadoLibre)")
    sub = p.add_subparsers(dest="cmd")

    p_run = sub.add_parser("run", help="Corre una pasada (default)")
    p_run.add_argument("--dry-run", action="store_true",
                       help="No notifica ni persiste; solo imprime resultados")
    p_run.add_argument("--limit", type=int, default=None,
                       help="Limita la cantidad de propiedades nuevas a procesar (testing)")
    p_run.add_argument("--notify-first-run", action="store_true",
                       help="Notifica también en la primera corrida (default: backfill silencioso)")
    p_run.add_argument("--backfill", action="store_true",
                       help="Marca todo como visto SIN notificar (para no spamear tras el alta)")

    sub.add_parser("login", help="Inicia sesión en MercadoLibre (headful) y guarda la sesión")

    p_dig = sub.add_parser("digest", help="Manda por Telegram el top-5 (correr 1 vez/día)")
    p_dig.add_argument("-n", type=int, default=5, help="Cantidad (default 5)")
    p_dig.add_argument("--all", action="store_true",
                       help="Incluir también las que no pasan todos los filtros duros")

    p_add = sub.add_parser("add", help="Ingiere propiedades marcadas (con status), las guarda")
    p_add.add_argument("urls", nargs="*", help="URLs de MercadoLibre (o usar --file/--html)")
    p_add.add_argument("--file", default="marcadas.txt",
                       help="Archivo con una URL por línea (default: marcadas.txt)")
    p_add.add_argument("--html", default=None,
                       help="Página de Favoritos de ML guardada (.html) — parseo offline con status")

    # permitir flags de run sin subcomando (python -m scraprop --dry-run)
    p.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--limit", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--notify-first-run", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--backfill", action="store_true", help=argparse.SUPPRESS)

    args = p.parse_args()
    if args.cmd == "login":
        login()
        return
    if args.cmd == "digest":
        pipeline.digest(n=args.n, only_passed=not args.all)
        return
    if args.cmd == "add":
        if args.html:
            pipeline.ingest_html(args.html)
            return
        urls = list(args.urls)
        fpath = Path(args.file)
        if not urls and fpath.exists():
            urls = fpath.read_text().splitlines()
            print(f"📂 Leyendo URLs de {fpath}")
        pipeline.ingest(urls)
        return
    pipeline.run(dry_run=args.dry_run, limit=args.limit,
                 notify_first_run=args.notify_first_run, force_backfill=args.backfill)


if __name__ == "__main__":
    main()
