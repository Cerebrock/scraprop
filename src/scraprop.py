# https://pypi.org/project/cloudscraper/
# https://dev.to/fernandezpablo/scrappeando-propiedades-con-python-4cp8

"""
Property Scraper: Scrapes property links from various real estate sites and sends new ones via Telegram.
"""
from time import sleep
from typing import List, Dict
import os
from datetime import datetime # Import datetime for timestamps

# Import from our modules
from scraper import create_scraper, extract_ads, extract_property_details, parse_search_details, test_all_scrapers
from utils import (
    load_environment, load_urls, split_seen_and_unseen, update_history,
    notify_telegram, save_properties_to_csv, format_telegram_message, get_html
)
from llm_scorer import get_scorer


def format_enhanced_telegram_message(property_details: dict, search_details: tuple) -> str:
    """Format a Telegram message with LLM analysis and scoring."""
    message = ""
    
    # Add LLM analysis if available
    if 'llm_analysis' in property_details and property_details['llm_analysis']:
        analysis = property_details['llm_analysis']
        score = property_details.get('score', 0)
        score_breakdown = property_details.get('score_breakdown', {})
        
        message += f"⭐ <b>SCORE: {score}</b>\n"
        
        if score_breakdown:
            message += "\n📊 <b>Score Breakdown:</b>\n"
            for reason, points in score_breakdown.items():
                message += f"  • {reason}: +{points}\n"
        
        message += f"\n🏠 <b>Analysis:</b>\n"
        message += f"  📍 Neighborhood: {analysis.get('neighbourhood', 'N/A')}\n"
        message += f"  🌳 Ground Floor: {'Yes' if analysis.get('is_ground_floor') else 'No'}\n"
        message += f"  🌿 Outdoor Space: {'Yes' if analysis.get('has_outdoor_space') else 'No'}\n"
        if analysis.get('outdoor_space_type', 'none') != 'none':
            message += f"  🌸 Outdoor Type: {analysis.get('outdoor_space_type')}\n"
        
        # Add proximity information
        if analysis.get('near_important_avenue'):
            message += f"  🛣️ Near Important Avenue: Yes\n"
        if analysis.get('near_subway_train'):
            message += f"  🚇 Near Subway/Train: Yes\n"
            
        message += f"  📏 Surface: {analysis.get('surface_m2', 'N/A')}m²\n"
        message += f"  💰 Price: ${analysis.get('price_numeric', 'N/A'):,}\n"
        message += "\n"
    
    # Add basic property details
    if property_details.get('neighbourhood'):
        message += f"📍 Zona: {property_details['neighbourhood']}\n"
    if property_details.get('price'):
        message += f"💰 Precio: {property_details['price']}\n"
    if property_details.get('expenses'):
        message += f"💸 Expensas: {property_details['expenses']}\n"
    if property_details.get('surface'):
        message += f"📏 Sup.: {property_details['surface']}\n"
    if property_details.get('rooms'):
        message += f"🏠 Ambientes: {property_details['rooms']}\n"
    if property_details.get('upload_date'):
        message += f"📅 Publicado: {property_details['upload_date']}\n"
    if property_details.get('seen_date'):
        message += f"👁️ Visto: {property_details['seen_date']}\n"
    
    message += f"\n{property_details.get('url', '')}"
    return message


def main(max_properties: int = None):
    """Main function to run the property scraper."""
    # Add a prominent separator for each cron run
    print("\n" + "="*80)
    print(f"[{datetime.now()}] STARTING NEW SCRAPING RUN")
    print("="*80 + "\n")

    # Configuration
    # Ensure outputs directory exists
    os.makedirs('outputs', exist_ok=True)
    urls_fp = "urls_to_scrap.txt"
    history_fp = "outputs/seen.txt"
    csv_filename = "outputs/scraped_properties.csv"
    
    # Load environment variables
    env = load_environment()
    if not env['telegram_bot_id'] or not env['telegram_id']:
        print("Error: Telegram bot credentials not found in .env file")
        return
    
    # Initialize LLM scorer
    scorer = get_scorer()
    if scorer:
        print("✅ LLM Scorer initialized successfully")
    else:
        print("⚠️  LLM Scorer not available - continuing without scoring")
    
    # Initialize Google Sheets early and share link if created
    sheets_manager = None
    try:
        from sheets_manager import get_sheets_manager
        sheets_manager = get_sheets_manager()
        if sheets_manager:
            print("✅ Google Sheets initialized successfully")
            sheet_url = sheets_manager.get_sheet_url()
            if sheet_url:
                print()
                print("📊" + "="*60)
                print("📊 LIVE GOOGLE SHEET READY!")
                print("📊" + "="*60)
                print(f"🔗 Sheet URL: {sheet_url}")
                print("💡 You can monitor real-time updates at this link!")
                print("🚀 Properties will be automatically updated as scraping progresses")
                print("📊" + "="*60)
                print()
        else:
            print("ℹ️  Google Sheets not configured (add credentials to enable)")
    except Exception as e:
        print(f"⚠️  Google Sheets initialization error: {e}")
    
    # Load URLs to scrape
    try:
        urls = load_urls(urls_fp)
    except FileNotFoundError:
        print(f"Error: {urls_fp} not found")
        return
    
    if not urls:
        print("No URLs found to scrape")
        return
    
    print(f"Found {len(urls)} URLs to scrape")
    if max_properties:
        print(f"🔬 TEST MODE: Limited to {max_properties} properties")
    
    # Store all scraped properties for CSV
    all_properties: List[Dict] = []
    property_count = 0
    
    # Process each URL
    for url in urls:
        if max_properties and property_count >= max_properties:
            print(f"[{datetime.now()}] 🔬 Reached property limit of {max_properties}")
            break
            
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                print(f"[{datetime.now()}] Scraping: {url}")
                
                # Use the improved get_html function with strategy selection
                strategy = 'playwright' if 'zonaprop' in url else 'default'
                html_content = get_html(url, strategy=strategy)
                
                if not html_content:
                    print(f"[{datetime.now()}] Failed to get HTML content from {url}")
                    break
                
                ads = list(extract_ads(url, html_content))
                
                # Remove duplicates
                ads = [dict(t) for t in {tuple(d.items()) for d in ads}]
                seen, unseen = split_seen_and_unseen(ads, history_fp, sheets_manager)
                
                print(f"[{datetime.now()}] {len(seen)} seen, {len(unseen)} unseen for {url}")
                
                # Note: We are no longer processing 'seen' ads in detail here to avoid hitting the
                # max_properties limit before we get to the new ones. The CSV backup will be created
                # from the 'all_properties' list which only contains new items from this run.
                
                # Process unseen ads for both CSV and notifications
                if unseen:
                    search_details = parse_search_details(url)
                    
                    newly_processed_urls = []
                    for ad in unseen:
                        if max_properties and property_count >= max_properties:
                            break
                        try:
                            # Fetch property details once
                            ad_html = get_html(ad['url'])
                            if ad_html:
                                property_details = extract_property_details(ad['url'], ad_html)
                                
                                # Add LLM analysis if scorer is available
                                if scorer:
                                    print(f"[{datetime.now()}] 🤖 Analyzing new property with LLM: {ad['url']}...")
                                    property_details = scorer.analyze_property(property_details)
                                    sleep(1)  # Rate limiting for LLM API
                                
                                # Add to list for final CSV backup
                                all_properties.append(property_details)
                                property_count += 1
                                newly_processed_urls.append(ad['url'])
                                
                                # Append to Google Sheet one-by-one
                                if sheets_manager:
                                    print(f"[{datetime.now()}] 📊 Appending to Google Sheet: {ad['url']}")
                                    sheets_manager.append_property(property_details)
                                
                                # Send Telegram notification if it has a positive score
                                if property_details.get('score', 0) > 0:
                                    message = format_enhanced_telegram_message(property_details, search_details)
                                    success = notify_telegram(env['telegram_bot_id'], env['telegram_id'], message)
                                    if success:
                                        print(f"[{datetime.now()}]  - Telegram Notification sent for: {ad['url']}")
                                    else:
                                        print(f"[{datetime.now()}] ❌ Failed to send notification for: {ad['url']}")
                                    sleep(1) # Rate limiting
                                    
                        except Exception as e:
                            print(f"[{datetime.now()}] Error processing unseen ad {ad['url']}: {e}")
                    
                    # Update history with the newly processed URLs
                    if newly_processed_urls:
                        update_history(history_fp, newly_processed_urls)
                
                break  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                print(f"[{datetime.now()}] Error scraping {url} (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    sleep(5)  # Wait before retry
                else:
                    print(f"[{datetime.now()}] Failed to scrape {url} after {max_retries} attempts")
    
    # After scraping all URLs, save all properties to the CSV for backup
    if all_properties:
        print(f"\n[{datetime.now()}] 💾 Saving {len(all_properties)} properties to CSV backup...")
        save_properties_to_csv(all_properties, csv_filename)
    
    print(f"[{datetime.now()}] Scraping and analysis complete!")


if __name__ == "__main__":
    # Test scrapers (comment out when running main workflow)
    # test_all_scrapers()
    
    # Run main workflow
    main()
