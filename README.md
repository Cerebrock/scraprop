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
- **Multi-source scraping**: Zonaprop, Argenprop, and MercadoLibre
- **LLM Analysis**: AI-powered property scoring and analysis using Google Gemini
- **Smart filtering**: Penalizes commercial properties ("local", "deposito") with -15 points
- **Live Google Sheets**: Real-time updates to shareable Google Sheets (optional)
- **CSV Export**: All scraped data saved to `outputs/scraped_properties.csv`
- **Telegram notifications**: New high-scoring properties sent via Telegram
- **Duplicate prevention**: Tracks seen properties to avoid spam
- **Detailed extraction**: Price, expenses, neighbourhood, surface, rooms, descriptions, and more

## Setup
1. **Clone the repo**
2. **Install dependencies** (preferably in a conda or venv):
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up environment variables** in a `.env` file:
   ```env
   # Required for Telegram notifications
   TELEGRAM_BOT_ID=your_bot_id
   TELEGRAM_ID=your_telegram_user_id
   
   # Required for LLM analysis
   GEMINI_API_KEY=your_gemini_api_key
   
   # Optional: Google Sheets integration (see setup guide)
   GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json
   GOOGLE_SHEETS_SHARE_EMAIL=your-email@gmail.com
   # GOOGLE_SHEET_ID=your_existing_sheet_id
   ```
4. **Add search URLs** to `urls_to_scrap.txt` (one per line)

## Google Sheets Integration (Optional)

Set up live Google Sheets for real-time property data viewing:

1. **Follow the detailed setup guide**: See `setup_google_sheets.md`
2. **Test the integration**: Run `python test_google_sheets.py`
3. **Features**:
   - Automatic updates with every scraper run
   - Data sorted by LLM score (best properties first) 
   - Shareable with colleagues or family
   - Includes timestamps and all analysis data
   - **Shared history**: Seen URLs tracked in Google Sheet (no more duplicate notifications)

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

### CSV Export
All scraped properties are saved to `outputs/scraped_properties.csv` with columns:
- Basic: url, price, expenses, neighbourhood, surface, rooms, description
- Analysis: score, score_breakdown, llm_neighbourhood, llm_surface_m2, etc.

### Google Sheets (if configured)
- **Live updates**: Real-time data accessible from anywhere
- **Sorted by score**: Best properties appear at the top
- **Shareable**: Easy to share with others
- **Timestamped**: Last update time included

### Telegram Notifications
High-scoring new properties are sent with LLM analysis:
```
⭐ SCORE: 23

📊 Score Breakdown:
  • Location (Belgrano): +10
  • Ground Floor: +10
  • Outdoor Space: +3

🏠 Analysis:
  📍 Neighborhood: Belgrano
  🌳 Ground Floor: Yes
  🌿 Outdoor Space: Yes
  📏 Surface: 80m²
  💰 Price: $500,000

📍 Zona: Belgrano
💰 Precio: $500.000
📏 Sup.: 80 m²
🏠 Ambientes: 3

https://www.zonaprop.com.ar/propiedades/...
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

