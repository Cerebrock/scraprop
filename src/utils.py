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


def get_history(history_fp: str) -> List[str]:
    """Load seen URLs from history file."""
    try:
        with open(history_fp, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []


def update_history(history_fp: str, new_urls: List[str]) -> None:
    """Append new URLs to history file."""
    with open(history_fp, "a") as f:
        for url in new_urls:
            f.write(url + "\n")


def split_seen_and_unseen(ads: List[Dict], history_fp: str) -> Tuple[List[Dict], List[Dict]]:
    """Split ads into seen and unseen based on history."""
    history = get_history(history_fp)
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


def save_properties_to_csv(properties: list, filename: str = "scraped_properties.csv", sheets_manager=None) -> None:
    """Save scraped properties to CSV file, ensuring all fields are present including LLM analysis."""
    if not properties:
        print("No properties to save.")
        return
    
    # Ensure all expected columns are present, including LLM analysis fields
    base_columns = ['url', 'price', 'expenses', 'neighbourhood', 'surface', 'rooms', 'upload_date', 'seen_date', 'description']
    llm_columns = [
        'score', 'score_breakdown', 
        'llm_neighbourhood', 'llm_is_ground_floor', 'llm_has_outdoor_space', 
        'llm_outdoor_space_type', 'llm_surface_m2', 'llm_price_numeric',
        'llm_near_important_avenue', 'llm_near_subway_train'
    ]
    all_columns = base_columns + llm_columns
    
    df = pd.DataFrame(properties)
    
    # Ensure base columns exist
    for col in base_columns:
        if col not in df:
            df[col] = None
    
    # Extract LLM analysis data into separate columns
    if 'llm_analysis' in df.columns:
        for idx, row in df.iterrows():
            llm_analysis = row.get('llm_analysis')
            if llm_analysis and isinstance(llm_analysis, dict):
                df.at[idx, 'llm_neighbourhood'] = llm_analysis.get('neighbourhood', '')
                df.at[idx, 'llm_is_ground_floor'] = llm_analysis.get('is_ground_floor', False)
                df.at[idx, 'llm_has_outdoor_space'] = llm_analysis.get('has_outdoor_space', False)
                df.at[idx, 'llm_outdoor_space_type'] = llm_analysis.get('outdoor_space_type', 'none')
                df.at[idx, 'llm_surface_m2'] = llm_analysis.get('surface_m2', 0)
                df.at[idx, 'llm_price_numeric'] = llm_analysis.get('price_numeric', 0)
                df.at[idx, 'llm_near_important_avenue'] = llm_analysis.get('near_important_avenue', False)
                df.at[idx, 'llm_near_subway_train'] = llm_analysis.get('near_subway_train', False)
    
    # Ensure LLM columns exist
    for col in llm_columns:
        if col not in df:
            if col == 'score':
                df[col] = 0
            elif col == 'score_breakdown':
                df[col] = ''
            elif col in ['llm_is_ground_floor', 'llm_has_outdoor_space', 'llm_near_important_avenue', 'llm_near_subway_train']:
                df[col] = False
            elif col in ['llm_surface_m2', 'llm_price_numeric']:
                df[col] = 0
            else:
                df[col] = ''
    
    # Convert score_breakdown dict to string for CSV
    if 'score_breakdown' in df.columns:
        for idx, row in df.iterrows():
            score_breakdown = row.get('score_breakdown')
            if score_breakdown and isinstance(score_breakdown, dict):
                breakdown_str = '; '.join([f"{k}: {'+' if v >= 0 else ''}{v}" for k, v in score_breakdown.items()])
                df.at[idx, 'score_breakdown'] = breakdown_str
    
    # Select and reorder columns
    df = df[all_columns]
    
    # Check if file exists to append or create new
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        # Ensure existing df has all columns
        for col in all_columns:
            if col not in existing_df.columns:
                if col == 'score':
                    existing_df[col] = 0
                elif col == 'score_breakdown':
                    existing_df[col] = ''
                elif col in ['llm_is_ground_floor', 'llm_has_outdoor_space', 'llm_near_important_avenue', 'llm_near_subway_train']:
                    existing_df[col] = False
                elif col in ['llm_surface_m2', 'llm_price_numeric']:
                    existing_df[col] = 0
                else:
                    existing_df[col] = ''
        
        existing_df = existing_df[all_columns]  # Reorder existing df columns
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['url'], keep='last')
        combined_df.to_csv(filename, index=False)
        print(f"Appended {len(df)} properties to {filename}")
    else:
        df.to_csv(filename, index=False)
        print(f"Saved {len(df)} properties to {filename}")
    
    # Print summary of LLM analysis
    if 'score' in df.columns:
        # Count properties that have LLM analysis (non-null llm_neighbourhood)
        analyzed_count = len(df[df['llm_neighbourhood'].notna()])
        scored_count = len(df[df['score'] > 0])
        if analyzed_count > 0:
            avg_score = df['score'].mean()  # Average of all scores including 0
            max_score = df['score'].max()
            min_score = df['score'].min()
            print(f"🤖 LLM Analysis: {analyzed_count}/{len(df)} properties analyzed")
            print(f"📊 Scores: {scored_count} with score > 0, Average {avg_score:.1f}, Range {min_score} to {max_score}")
    
    # Update Google Sheets if configured
    if sheets_manager:
        try:
            print("📊 Updating Google Sheets...")
            success = sheets_manager.update_sheet(properties, clear_first=True)
            if success:
                print(f"✅ Google Sheets updated successfully!")
            else:
                print("⚠️  Google Sheets update failed")
        except Exception as e:
            print(f"⚠️  Google Sheets update error: {e}")
    elif not sheets_manager:
        # Only try to get one if not passed (for backward compatibility)
        try:
            sheets_manager = get_sheets_manager()
            if sheets_manager:
                print("📊 Updating Google Sheets...")
                success = sheets_manager.update_sheet(properties, clear_first=True)
                if success:
                    print(f"✅ Google Sheets updated successfully!")
                    sheet_url = sheets_manager.get_sheet_url()
                    if sheet_url:
                        print(f"🔗 View live data: {sheet_url}")
                else:
                    print("⚠️  Google Sheets update failed")
            else:
                print("ℹ️  Google Sheets not configured (add credentials to enable)")
        except Exception as e:
            print(f"⚠️  Google Sheets update error: {e}") 