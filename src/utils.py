"""
Utility functions for the property scraper.
"""
import os
from typing import List, Dict, Tuple
import pandas as pd
import requests
from dotenv import load_dotenv
from scraper import create_scraper, PlaywrightScraper
from sheets_manager import get_sheets_manager
from datetime import datetime


def load_environment():
    """Load environment variables from .env file."""
    load_dotenv()
    return {
        'telegram_bot_id': os.getenv("TELEGRAM_BOT_ID"),
        'telegram_id': os.getenv("TELEGRAM_ID"),
        'gemini_api_key': os.getenv("GEMINI_API_KEY")
    }


def get_html(url: str, strategy: str = 'default') -> str:
    """
    Fetches HTML content from a URL using a specified strategy.
    
    Args:
        url: The URL to fetch.
        strategy: 'default' for cloudscraper, 'playwright' for a full browser.
        
    Returns:
        The HTML content as a string, or an empty string if fetching fails.
    """
    # For Zonaprop, try cloudscraper first (Open Graph meta tags work with basic HTTP)
    if 'zonaprop.com.ar' in url and strategy == 'playwright':
        print(f"  (Trying cloudscraper first for Zonaprop: {url[:70]}...)")
        try:
            scraper = create_scraper()
            response = scraper.get(url)
            if response.status_code == 200:
                # Check if we got meaningful content (not just a Cloudflare block page)
                if 'og:title' in response.text or 'property' in response.text:
                    print(f"  ✅ Cloudscraper worked for Zonaprop!")
                    return response.text
                else:
                    print(f"  ⚠️  Cloudscraper got blocked content, trying Playwright...")
            else:
                print(f"  ⚠️  Cloudscraper failed (status: {response.status_code}), trying Playwright...")
        except Exception as e:
            print(f"  ⚠️  Cloudscraper failed: {e}, trying Playwright...")
    
    if strategy == 'playwright':
        print(f"  (Using Playwright for: {url[:70]}...)")
        browser_scraper = None
        try:
            browser_scraper = PlaywrightScraper()
            return browser_scraper.get(url)
        except Exception as e:
            print(f"  ❌ Playwright fetch failed: {e}")
            return ""
        finally:
            if browser_scraper:
                browser_scraper.close()
    
    # Default strategy: cloudscraper
    try:
        scraper = create_scraper()
        response = scraper.get(url)
        if response.status_code == 200:
            return response.text
        else:
            print(f"  ❌ Cloudscraper fetch failed (status: {response.status_code})")
            return ""
    except Exception as e:
        print(f"  ❌ Cloudscraper fetch failed: {e}")
        return ""


def load_urls(file_path: str) -> List[str]:
    """Load URLs to scrape from a file."""
    with open(file_path, "r") as inp:
        return [line.strip() for line in inp if line.strip()]


def get_history(history_fp: str, sheets_manager=None) -> List[str]:
    """Load seen URLs from history file and/or Google Sheet."""
    seen_urls = []
    
    # First, try to get from Google Sheet if available
    if sheets_manager:
        try:
            sheet_urls = sheets_manager.get_seen_urls()
            if sheet_urls:
                seen_urls.extend(sheet_urls)
                print(f"📊 Retrieved {len(sheet_urls)} seen URLs from Google Sheet")
        except Exception as e:
            print(f"⚠️  Error getting URLs from Google Sheet: {e}")
    
    # Also get from local file as backup/fallback
    try:
        with open(history_fp, "r") as f:
            file_urls = [line.strip() for line in f if line.strip()]
            if file_urls:
                seen_urls.extend(file_urls)
                print(f"📁 Retrieved {len(file_urls)} seen URLs from local file")
    except FileNotFoundError:
        if not sheets_manager:  # Only print if no sheets manager (so we're relying on file)
            print(f"📁 No local history file found at {history_fp}")
    
    # Remove duplicates while preserving order
    unique_seen_urls = []
    seen_set = set()
    for url in seen_urls:
        if url not in seen_set:
            unique_seen_urls.append(url)
            seen_set.add(url)
    
    if sheets_manager and unique_seen_urls:
        print(f"📋 Total unique seen URLs: {len(unique_seen_urls)}")
    
    return unique_seen_urls


def update_history(history_fp: str, new_urls: List[str]) -> None:
    """Append new URLs to history file."""
    with open(history_fp, "a") as f:
        for url in new_urls:
            f.write(url + "\n")


def split_seen_and_unseen(ads: List[Dict], history_fp: str, sheets_manager=None) -> Tuple[List[Dict], List[Dict]]:
    """Split ads into seen and unseen based on history from file and/or Google Sheet."""
    history = get_history(history_fp, sheets_manager)
    seen = []
    unseen = []
    
    for ad in ads:
        if ad['url'] in history:
            seen.append(ad)
        else:
            unseen.append(ad)
    
    return seen, unseen


def notify_telegram(bot_id: str, user_id: str, message: str) -> bool:
    """Send a message via Telegram bot."""
    try:
        url = f"https://api.telegram.org/bot{bot_id}/sendMessage"
        data = {
            "chat_id": user_id,
            "text": message,
            "parse_mode": "HTML"
        }
        response = requests.post(url, data=data)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False


def format_property_details(details: dict) -> str:
    """Format all available property details for Telegram message."""
    lines = []
    if details.get('neighbourhood'):
        lines.append(f"📍 Zona: {details['neighbourhood']}")
    if details.get('price'):
        lines.append(f"💰 Precio: {details['price']}")
    if details.get('expenses'):
        lines.append(f"💸 Expensas: {details['expenses']}")
    if details.get('surface'):
        lines.append(f"📏 Sup.: {details['surface']}")
    if details.get('rooms'):
        lines.append(f"🏠 Ambientes: {details['rooms']}")
    if details.get('upload_date'):
        lines.append(f"📅 Publicado: {details['upload_date']}")
    if details.get('seen_date'):
        lines.append(f"👁️ Visto: {details['seen_date']}")
    return '\n'.join(lines)


def format_telegram_message(ad_url: str, search_details: tuple, property_details: dict = None) -> str:
    """Format a Telegram message with property and search details."""
    message = ""
    if property_details:
        message += format_property_details(property_details) + "\n\n"
    else:
        zone, price, min_surface = search_details
        if zone:
            message += f"Zona: {zone}\n"
        if price:
            message += f"Precio: {price}\n"
        if min_surface:
            message += f"Sup. mínima: {min_surface} m2\n"
        if message:
            message += "\n"
    message += ad_url
    return message


def save_properties_to_csv(properties: list, filename: str = "scraped_properties.csv") -> None:
    """Save scraped properties to a CSV file for backup. This function no longer handles Google Sheets updates."""
    if not properties:
        print("No properties to save to CSV.")
        return

    # Define the column order to match the Google Sheet for consistency
    csv_columns = [
        'last_updated', 'score', 'llm_price_numeric', 'llm_surface_m2',
        'llm_is_ground_floor', 'llm_has_outdoor_space', 'llm_near_important_avenue', 'llm_near_subway_train',
        'url', 'llm_neighbourhood', 'llm_outdoor_space_type',
        'price', 'surface', 'neighbourhood', 'rooms', 'expenses', 'description',
        'score_breakdown', 'upload_date', 'seen_date'
    ]
    
    df = pd.DataFrame(properties)
    
    # Add last_updated timestamp
    df['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Extract LLM analysis data into separate columns
    if 'llm_analysis' in df.columns:
        analysis_df = df['llm_analysis'].apply(lambda x: pd.Series(x) if isinstance(x, dict) else pd.Series())
        # Add 'llm_' prefix to columns from analysis
        analysis_df.columns = ['llm_' + str(col) for col in analysis_df.columns]
        df = pd.concat([df.drop(['llm_analysis'], axis=1), analysis_df], axis=1)

    # Format score breakdown
    if 'score_breakdown' in df.columns:
        df['score_breakdown'] = df['score_breakdown'].apply(
            lambda x: '; '.join([f"{k}: {'+' if v >= 0 else ''}{v}" for k, v in x.items()]) if isinstance(x, dict) else ''
        )

    # Ensure all columns exist, fill missing with empty string
    for col in csv_columns:
        if col not in df.columns:
            df[col] = ''
    
    # Reorder columns for the final CSV
    df = df[csv_columns]
    
    # Save to CSV
    try:
        df.to_csv(filename, index=False)
        print(f"✅ Successfully saved {len(df)} properties to {filename}")
    except Exception as e:
        print(f"❌ Error saving properties to {filename}: {e}") 