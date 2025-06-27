"""
Utility functions for the property scraper.
"""
import os
from typing import List, Dict, Tuple
import pandas as pd
import requests
from dotenv import load_dotenv


def load_environment():
    """Load environment variables from .env file."""
    load_dotenv()
    return {
        'telegram_bot_id': os.getenv("TELEGRAM_BOT_ID"),
        'telegram_id': os.getenv("TELEGRAM_ID")
    }


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
        lines.append(f"Zona: {details['neighbourhood']}")
    if details.get('price'):
        lines.append(f"Precio: {details['price']}")
    if details.get('expenses'):
        lines.append(f"Expensas: {details['expenses']}")
    if details.get('surface'):
        lines.append(f"Sup.: {details['surface']}")
    if details.get('rooms'):
        lines.append(f"Ambientes: {details['rooms']}")
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
    """Save scraped properties to CSV file, ensuring all fields are present."""
    if not properties:
        print("No properties to save.")
        return
    # Ensure all expected columns are present
    columns = ['url', 'price', 'expenses', 'neighbourhood', 'surface', 'rooms']
    df = pd.DataFrame(properties)
    for col in columns:
        if col not in df:
            df[col] = None
    df = df[columns]
    # Check if file exists to append or create new
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename)
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['url'], keep='last')
        combined_df.to_csv(filename, index=False)
        print(f"Appended {len(df)} properties to {filename}")
    else:
        df.to_csv(filename, index=False)
        print(f"Saved {len(df)} properties to {filename}") 