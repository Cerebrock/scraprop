# scraprop — monitor de compra de propiedades

Monitorea nuevas publicaciones de **MercadoLibre Inmuebles (venta)** en barrios target,
deduplica, las puntúa con un LLM (Gemini) según reglas de compra y manda cada nueva
propiedad válida por **Telegram**, guardando todo en SQLite + CSV. Corre local (cron).

## Reglas de compra

**Filtros duros** (si no cumple, se descarta):
- Espacio exterior: balcón, terraza, jardín o patio.
- Barrio ∈ Chacarita, Coghlan, Palermo, Belgrano, Saavedra, Núñez, Florida Este,
  Vicente López, Colegiales, Villa Urquiza.
- A menos de ~4 cuadras de una avenida principal, subte o tren.
- Superficie total ≥ 90 m².
- Precio en USD entre 95.000 y 200.000.
- Publicada hace menos de 30 días.

**Scoring** (ordena prioridad; suma de puntos):
- Exterior (el mejor): jardín 3, terraza 2, balcón 1, patio 1.
- Barrio: Belgrano/Saavedra/Núñez 3; Florida Este/Vte López/Colegiales/Villa Urquiza 2;
  Chacarita/Coghlan/Palermo 1.
- Precio: 95–120k → 1; 120–150k → 2; 150–200k → 0,5.

Todo se ajusta en [scraprop/config.py](scraprop/config.py).

## Arquitectura

```
scraprop/
  config.py      reglas de negocio + settings (.env) + URLs de búsqueda ML
  models.py      Listing, ScoreResult
  db.py          SQLite (dedup + histórico)
  dedup.py       id canónico + firma de contenido (anti-repost)
  fetch.py       browser stealth (patchright) con sesión persistida
  sources/       adapters (mercadolibre activo; base.py para sumar otros)
  scorer.py      extracción Gemini + filtros duros + scoring (fallback heurístico)
  notify.py      Telegram
  pipeline.py    orquestación de una pasada
  __main__.py    CLI
data/            scraprop.db, scraped.csv, storage_state.json (gitignored)
```

### Scraping de MercadoLibre
ML aplica anti-bot agresivo: a las requests planas devuelve un *Challenge*, y tras varias
requests anónimas desde una IP muestra un **muro de login** ("Para continuar, ingresá a tu
cuenta"). Por eso se usa **Playwright stealth** (`patchright`) + **sesión autenticada**:

1. Una vez: `python -m scraprop login` abre un browser, iniciás sesión en ML (usá una cuenta
   secundaria/descartable) y se guarda la sesión en `data/storage_state.json`.
2. Las corridas reutilizan esa sesión (límites de rate mucho más altos que anónimo).

Eficiencia: un solo browser por pasada, sesión persistida, pacing con jitter entre requests,
se parsean las cards de búsqueda y se **prefiltra** (precio/superficie/visto) antes de bajar
cada detalle y llamar al LLM. Si igual aparece el muro de login, el scraper lo detecta y
avisa que corras `login` de nuevo.

> **Emprendimientos/pozo** ("edificio en…", "desde U$S…") se excluyen explícitamente
> (`ML_EXCLUDE_EMPRENDIMIENTOS`).

### Búsquedas fijas (`searches.txt`) y anti-ban
Las URLs a consultar se definen en `searches.txt` (una por línea). Por defecto trae **3
búsquedas con polígono** dibujado a mano (zona apta), para PH / casas / departamentos. Pocas
URLs + sesión autenticada + pacing con jitter + solo página 1 + detalle solo de las nuevas →
riesgo de ban bajo. Para cambiar la zona, dibujá de nuevo en ML y pegá la URL acá.

### Usar tu sesión REAL de Chrome (opción anti-ban)
En vez de `login`, podés apuntar a tu perfil de Chrome ya logueado (en `.env`):
```
SCRAPROP_CHROME_PROFILE=/Users/<vos>/Library/Application Support/Google/Chrome
SCRAPROP_CHROME_PROFILE_DIR=Default        # o "Profile 2", etc.
SCRAPROP_CHROME_CHANNEL=chrome
```
⚠️ Chrome debe estar **cerrado** en ese perfil durante las corridas (el perfil se bloquea).
Para que conviva con el cron, lo ideal es un **perfil dedicado** logueado en ML, que no uses
para navegar.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
cp .env.example .env       # completar TELEGRAM_BOT_ID, TELEGRAM_ID; GEMINI_API_KEY ya viene
python -m scraprop login   # iniciar sesión en ML una vez (guarda la sesión)
```

`.env`:
```
TELEGRAM_BOT_ID=...
TELEGRAM_ID=...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-lite-latest
USD_ARS=            # opcional, solo si aparecen cards en ARS
```

## Uso

```bash
python -m scraprop login                  # (una vez) iniciar sesión en ML
python -m scraprop --dry-run --limit 5    # prueba: no notifica ni persiste
python -m scraprop --limit 3              # corrida real acotada
python -m scraprop                         # corrida completa (monitoreo)
python -m scraprop digest                  # manda el top-5 por Telegram (1 vez/día por cron)
SCRAPROP_HEADFUL=1 python -m scraprop      # con ventana de browser (más difícil de bloquear)
bash setup_cron.sh                         # cron: monitoreo c/30min + digest diario 9:00
```

### Propiedades marcadas a mano (favoritos) + columna `status`
Cada propiedad guarda su `status` (`activa` / `pausada` / `finalizada` / `no disponible`) y un
flag `tracked` (1 = marcada por vos). Para ingerir tus favoritos:

```bash
# desde tu página de Favoritos de ML guardada como .html (offline, trae el status por card)
python -m scraprop add --html ~/Downloads/Favoritos.html
# o desde URLs sueltas / un archivo marcadas.txt (requiere sesión, baja el detalle en vivo)
python -m scraprop add "https://...MLA-123..."
python -m scraprop add            # lee marcadas.txt
```

### Notificaciones
- **Por propiedad**: alerta con emojis que resaltan las ventajas (barrio, espacio exterior,
  banda de precio, cercanía a transporte, amplitud) + link.
- **Digest diario**: tabla top-5 de las mejores puntuadas (excluye finalizadas) con links.

La **primera corrida real es un backfill silencioso**: carga el inventario actual como
"visto" sin notificar. A partir de la segunda, te llega por Telegram cada propiedad *nueva*
que cumpla los filtros (lo que aproxima "publicada hace poco", ya que ML oculta la fecha).
Para notificar también en la primera: `python -m scraprop --notify-first-run`.

## Notas
- "A 4 cuadras" se **estima por LLM** desde la dirección/descripción (ML da ubicación
  aproximada). Mejorable a futuro con dataset real de estaciones + avenidas.
- **Antigüedad < 30 días**: ML no expone la fecha de publicación, así que se aproxima con el
  backfill (lo nuevo = recién aparecido). El filtro `posted_days_ago` queda listo por si se
  suma otra fuente que sí dé la fecha.
- Sin `GEMINI_API_KEY` el scorer cae a una heurística por keywords (degradado pero funcional).
- **Seguridad**: `.env` ya no se trackea. Las credenciales viejas de Telegram quedaron en el
  historial de git — conviene rotar el bot token.
