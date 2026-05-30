"""Fetch con browser stealth para sortear el anti-bot ("Challenge / Robot") de MercadoLibre.

Eficiencia:
  - un solo browser/context por pasada (se reutiliza para todas las URLs),
  - se persiste storage_state.json para reusar las cookies del challenge entre corridas,
  - se espera a un selector objetivo en vez de tiempos fijos.

Usa `patchright` (fork undetected de Playwright) si está instalado; si no, cae a `playwright`.
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Optional

from . import config

# patchright es drop-in de la API sync de playwright
try:  # pragma: no cover - depende del entorno
    from patchright.sync_api import sync_playwright
    _ENGINE = "patchright"
except ImportError:  # pragma: no cover
    from playwright.sync_api import sync_playwright
    _ENGINE = "playwright"

_UA_TEMPLATE = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
_UA = _UA_TEMPLATE.format(major="148")  # fallback


def _clean_ua(browser) -> str:
    """UA consistente con la versión REAL del Chrome instalado, sin el token 'Headless'."""
    try:
        major = browser.version.split(".")[0]
        if major.isdigit():
            return _UA_TEMPLATE.format(major=major)
    except Exception:
        pass
    return _UA

def _launch(pw, headless: bool, channel: Optional[str]):
    """Lanza el browser. Por defecto usa el Chromium bundleado de patchright (instancia
    separada, sin conflicto con tu Chrome abierto). Si seteás SCRAPROP_CHROME_CHANNEL=chrome
    usa el Chrome real (más stealth) — pero requiere Chrome CERRADO para no colisionar."""
    channel = channel or os.getenv("SCRAPROP_CHROME_CHANNEL")  # None => Chromium bundleado
    if channel:
        try:
            b = pw.chromium.launch(headless=headless, channel=channel)
            print(f"  🛡️  patchright + Chrome real (channel={channel}, headless={headless})")
            return b
        except Exception as e:
            print(f"  ⚠️  No se pudo usar '{channel}' ({e}); uso Chromium bundleado.")
    b = pw.chromium.launch(headless=headless)
    print(f"  🛡️  patchright + Chromium bundleado (headless={headless})")
    return b


_CHALLENGE_MARKERS = ("Robot or human", "challenge-platform", "/_Incapsula_")
# Login-wall que ML muestra tras demasiadas requests anónimas
_LOGIN_WALL = ("para continuar, ingresa a tu cuenta", "para continuar, ingresá a tu cuenta")
# Contenedores que aparecen en una página real (listado, detalle o zero-results legítimo)
_CONTENT_MARKERS = ("ui-search-layout", "ui-search-result", "poly-card",
                    "ui-pdp", "ui-search-rescue--zrp")


def _looks_blocked(html: str) -> bool:
    if not html:
        return True
    low = html.lower()
    if any(m in html for m in _CHALLENGE_MARKERS):
        return True
    if any(m in low for m in _LOGIN_WALL):
        return True
    # Una página real siempre trae alguno de estos contenedores; si no, está bloqueada.
    return not any(m in html for m in _CONTENT_MARKERS)


class BrowserSession:
    """Maneja un browser stealth reutilizable con persistencia de cookies."""

    def __init__(self, headless: Optional[bool] = None, storage: Path = config.STORAGE_STATE,
                 min_interval: float = 2.0):
        if headless is None:
            headless = os.getenv("SCRAPROP_HEADFUL", "").lower() not in ("1", "true", "yes")
        self.headless = headless
        self.storage = storage
        self.min_interval = min_interval  # segundos mínimos entre requests (anti rate-limit)
        # Perfil de Chrome real (mejor anti-ban): usa tu sesión ya logueada.
        self.chrome_profile = os.path.expanduser(os.getenv("SCRAPROP_CHROME_PROFILE", "")) or None
        self.profile_dir = os.getenv("SCRAPROP_CHROME_PROFILE_DIR") or None  # ej "Default", "Profile 1"
        self.channel = os.getenv("SCRAPROP_CHROME_CHANNEL") or None          # ej "chrome"
        self._uses_profile = False
        self._last_req = 0.0
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def _pace(self) -> None:
        """Espera para respetar un intervalo mínimo entre requests, con jitter."""
        elapsed = time.time() - self._last_req
        wait = self.min_interval - elapsed + random.uniform(0, 1.5)
        if wait > 0:
            time.sleep(wait)
        self._last_req = time.time()

    def __enter__(self) -> "BrowserSession":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        self._pw = sync_playwright().start()
        ctx_kwargs = dict(
            user_agent=_UA,
            locale="es-AR",
            timezone_id="America/Argentina/Buenos_Aires",
            viewport={"width": 1366, "height": 900},
        )
        if self.chrome_profile:
            # Sesión real de Chrome (persistent context). Chrome debe estar CERRADO en ese
            # perfil, o el perfil estará bloqueado. Recomendado: un perfil dedicado logueado en ML.
            args = [f"--profile-directory={self.profile_dir}"] if self.profile_dir else []
            try:
                self._context = self._pw.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_profile,
                    channel=self.channel or "chrome",
                    headless=self.headless,
                    args=args,
                    **ctx_kwargs,
                )
            except Exception as e:
                raise RuntimeError(
                    f"No se pudo abrir el perfil de Chrome ({self.chrome_profile}). "
                    f"¿Está Chrome abierto en ese perfil? Cerralo o usá un perfil dedicado. "
                    f"Detalle: {e}"
                )
            self._uses_profile = True
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            print(f"  🌐 Usando tu sesión real de Chrome: {self.chrome_profile}"
                  f"{' / ' + self.profile_dir if self.profile_dir else ''}")
        else:
            self._browser = _launch(self._pw, self.headless, self.channel)
            ctx_kwargs["user_agent"] = _clean_ua(self._browser)  # matchea versión real, sin 'Headless'
            if self.storage.exists():
                ctx_kwargs["storage_state"] = str(self.storage)
            self._context = self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(45_000)
        if self._page is None:
            self._page = self._context.new_page()

    def get(self, url: str, wait_selector: Optional[str] = None, retries: int = 3,
            scroll: bool = False) -> str:
        """Carga una URL y devuelve el HTML ya renderizado (sorteando el challenge).

        scroll=True hace scroll para disparar el lazy-load (ML carga la descripción al
        acercarse al viewport).
        """
        for attempt in range(1, retries + 1):
            try:
                self._pace()
                self._page.goto(url, wait_until="domcontentloaded")
                if wait_selector:
                    try:
                        self._page.wait_for_selector(wait_selector, timeout=8_000)
                    except Exception:
                        pass  # seguimos: validamos por contenido abajo
                else:
                    self._page.wait_for_timeout(1200)
                if scroll:
                    try:
                        for _ in range(6):
                            self._page.mouse.wheel(0, 1200)
                            self._page.wait_for_timeout(200)
                    except Exception:
                        pass
                html = self._page.content()
                if not _looks_blocked(html):
                    return html
                # Challenge detectado: esperar a que el JS lo resuelva y reintentar
                print(f"  ⏳ Challenge detectado en {url[:60]}… esperando (intento {attempt})")
                self._page.wait_for_timeout(4000 * attempt)
                html = self._page.content()
                if not _looks_blocked(html):
                    return html
            except Exception as e:
                print(f"  ⚠️  Error cargando {url[:60]}… ({attempt}/{retries}): {e}")
                time.sleep(2)
        print(f"  ❌ Bloqueado/login-wall en {url[:70]}")
        print("     💡 Corré `python -m scraprop login` para iniciar sesión en ML y guardar la sesión.")
        return ""

    def save_state(self) -> None:
        if self._uses_profile:
            return  # el perfil de Chrome persiste sus propias cookies
        try:
            if self._context:
                self.storage.parent.mkdir(parents=True, exist_ok=True)
                self._context.storage_state(path=str(self.storage))
        except Exception as e:
            print(f"  ⚠️  No se pudo guardar storage_state: {e}")

    def close(self) -> None:
        self.save_state()
        for obj, meth in ((self._context, "close"), (self._browser, "close"), (self._pw, "stop")):
            try:
                if obj:
                    getattr(obj, meth)()
            except Exception:
                pass


def login(storage: Path = config.STORAGE_STATE) -> None:
    """Abre un browser headful para que inicies sesión en MercadoLibre una vez.

    La sesión autenticada (cookies) se guarda en storage_state.json y se reutiliza en cada
    corrida. Navegar logueado tiene límites de rate mucho más altos que anónimo.
    Recomendación: usá una cuenta secundaria/descartable de ML.
    """
    import json
    print("🔐 Abriendo MercadoLibre en una ventana propia (Chromium bundleado, separada de tu Chrome).")
    print("   Iniciá sesión en ESA ventana (clic en 'Ingresá').")
    pw = sync_playwright().start()
    # Forzamos Chromium bundleado: instancia separada garantizada, no se mezcla con tu Chrome.
    browser = pw.chromium.launch(headless=False)
    ctx = browser.new_context(
        locale="es-AR",
        timezone_id="America/Argentina/Buenos_Aires",
        viewport={"width": 1280, "height": 900},
    )
    page = ctx.new_page()
    page.goto("https://www.mercadolibre.com.ar/")
    try:
        input("\n👉 Cuando TERMINES de loguearte (veas tu nombre/cuenta), volvé acá y presioná ENTER… ")
    except (EOFError, KeyboardInterrupt):
        pass
    storage.parent.mkdir(parents=True, exist_ok=True)
    ctx.storage_state(path=str(storage))
    # feedback: ¿detectamos cookies de login?
    cookies = json.load(open(storage)).get("cookies", [])
    names = {c["name"] for c in cookies}
    logged = bool(names & {"orguseridp", "ssid", "p_uid"}) or len(cookies) >= 8
    print(f"\n{'✅' if logged else '⚠️'} Guardadas {len(cookies)} cookies en {storage}")
    if not logged:
        print("   ⚠️ NO parece que hayas quedado logueado (faltan cookies de sesión).")
        print("   Volvé a correr `python -m scraprop login` y asegurate de completar el ingreso.")
    browser.close()
    pw.stop()
