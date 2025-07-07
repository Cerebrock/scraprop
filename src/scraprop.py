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
                print(f"📊 Live Google Sheet: {sheet_url}")
                print("💡 You can monitor real-time updates at this link!")
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
                seen, unseen = split_seen_and_unseen(ads, history_fp)
                
                print(f"[{datetime.now()}] {len(seen)} seen, {len(unseen)} unseen for {url}")
                
                # Process seen ads for CSV only
                for ad in seen:
                    if max_properties and property_count >= max_properties:
                        break
                    try:
                        ad_html = get_html(ad['url'])
                        if ad_html:
                            property_details = extract_property_details(ad['url'], ad_html)
                            
                            # Add LLM analysis if scorer is available
                            if scorer:
                                print(f"[{datetime.now()}] 🤖 Analyzing property with LLM: {ad['url']}...")
                                property_details = scorer.analyze_property(property_details)
                                sleep(1)  # Rate limiting for LLM API
                            
                            all_properties.append(property_details)
                            property_count += 1
                            sleep(1)  # Be respectful to the servers
                    except Exception as e:
                        print(f"[{datetime.now()}] Error extracting details from {ad['url']}: {e}")
                
                # Process unseen ads for both CSV and notifications
                if unseen:
                    search_details = parse_search_details(url)
                    
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
                                
                                # Add to CSV data
                                all_properties.append(property_details)
                                property_count += 1
                                
                                # !!! Removed immediate Telegram notification sending
                                # if scorer and 'llm_analysis' in property_details:
                                #     message = format_enhanced_telegram_message(property_details, search_details)
                                # else:
                                #     message = format_telegram_message(ad['url'], search_details, property_details)
                                # 
                                # success = notify_telegram(env['telegram_bot_id'], env['telegram_id'], message)
                                # if success:
                                #     print(f"[{datetime.now()}] Notification sent for: {ad['url']}")
                                # else:
                                #     print(f"[{datetime.now()}] Failed to send notification for: {ad['url']}")
                                # sleep(1)  # Rate limiting
                        except Exception as e:
                            print(f"[{datetime.now()}] Error processing unseen ad {ad['url']}: {e}")
                            # Still try to send notification without details (this will be handled by post-processing now)
                            # message = format_telegram_message(ad['url'], search_details)
                            # notify_telegram(env['telegram_bot_id'], env['telegram_id'], message)
                    
                    # Update history with new URLs
                    new_urls = [ad['url'] for ad in unseen]
                    update_history(history_fp, new_urls)
                
                break  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                print(f"[{datetime.now()}] Error scraping {url} (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    sleep(5)  # Wait before retry
                else:
                    print(f"[{datetime.now()}] Failed to scrape {url} after {max_retries} attempts")
    
    # After scraping all URLs, sort properties by score and send them
    print(f"[{datetime.now()}] 🚀 Sorting and sending properties by score...")
    
    # Filter properties that have been scored and sort them by score
    scored_properties_to_notify = [prop for prop in all_properties if prop.get('score', 0) > 0]
    
    scored_properties_to_notify.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    TELEGRAM_BOT_TOKEN = env['telegram_bot_id']
    TELEGRAM_CHAT_ID = env['telegram_id']

    # Send separator message at the start of the batch
    if scored_properties_to_notify and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        separator_message = "—" * 30 + "\n🏠 NEW PROPERTY BATCH\n" + "—" * 30
        notify_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, separator_message)
        sleep(1)

    for prop in scored_properties_to_notify:
        # The search_details tuple (search_url, num_ads_found) is not directly available per property here.
        # We can pass a generic placeholder as format_enhanced_telegram_message expects it.
        # The important info is already in the property_details dict.
        message = format_enhanced_telegram_message(prop, ('Scraped from multiple searches', len(scored_properties_to_notify)))
        
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            success = notify_telegram(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, message)
            if success:
                print(f"[{datetime.now()}] Notification sent for: {prop.get('url', 'N/A')}")
            else:
                print(f"[{datetime.now()}] Failed to send notification for: {prop.get('url', 'N/A')}")
            sleep(1) # Add delay between sending messages
        else:
            print(f"[{datetime.now()}] Telegram BOT_TOKEN or CHAT_ID not set. Skipping Telegram notification.")
            print(f"[{datetime.now()}] --- Property Score: {prop.get('score', 0)} --- URL: {prop.get('url', 'N/A')}")
            print(message)

    # Save all properties to CSV after processing all URLs
    if all_properties:
        save_properties_to_csv(all_properties, csv_filename, sheets_manager)
        print(f"[{datetime.now()}] Scraped {len(all_properties)} total properties")
    
    print(f"[{datetime.now()}] Scraping and analysis complete!")


if __name__ == "__main__":
    # Test scrapers (comment out when running main workflow)
    # test_all_scrapers()
    
    # Run main workflow
    main()
