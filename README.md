# Property Scraper

Scrapes property listings from Zonaprop, Argenprop, and MercadoLibre, saving all details to a CSV and sending new listings via Telegram.

## Repo Structure
- `src/` — All main code modules (`scraprop.py`, `scraper.py`, `utils.py`)
- `tests/` — For future test scripts
- `urls_to_scrap.txt` — List of search URLs
- `outputs/scraped_properties.csv` — All scraped property data
- `outputs/seen.txt` — Tracks already-notified properties
- `.env` — Environment variables for Telegram
- `outputs/` — All output files (CSV, logs)

## Features
- Scrapes multiple real estate sources
- Extracts price, expenses (expensas), neighbourhood, surface, rooms, and more
- Saves all scraped data to `outputs/scraped_properties.csv`
- Sends new property links and details to Telegram
- Avoids duplicate notifications using a `seen.txt` file

## Setup
1. **Clone the repo**
2. **Install dependencies** (preferably in a conda or venv):
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up environment variables** in a `.env` file:
   ```env
   TELEGRAM_BOT_ID=your_bot_id
   TELEGRAM_ID=your_telegram_user_id
   ```
4. **Add search URLs** to `urls_to_scrap.txt` (one per line)

## Running
- To run the main workflow:
  ```bash
  python src/scraprop.py
  ```
- To test scrapers for each source:
  ```bash
  python src/scraper.py
  ```

## Output
- **CSV:** All scraped properties are saved to `outputs/scraped_properties.csv` with columns:
  - url, price, expenses, neighbourhood, surface, rooms
- **Telegram:** New listings are sent with details, e.g.:
  ```
  Zona: Belgrano
  Precio: $800000
  Expensas: $150000
  Sup. mínima: 60 m2
  Ambientes: 3
  https://departamento.mercadolibre.com.ar/MLA-2091232812-excelente-3-amb-flores-ver-descripcion-_JM
  ```

## Customization
- Add or remove search URLs in `urls_to_scrap.txt`
- Adjust scraping logic in `src/scraper.py` for new fields
- Change CSV filename in `src/scraprop.py` if needed

## Cron Example
To run every 6 hours and log output:
```cron
30 */6 * * * /path/to/python /path/to/scraprop/src/scraprop.py >> /path/to/scraprop/outputs/logs/scraprop-cron.log
```

## Tests
- Place test scripts in the `tests/` directory.
- (Coming soon: example test scripts for scrapers and utilities)

---
For questions or improvements, open an issue or PR.

