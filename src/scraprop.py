# https://pypi.org/project/cloudscraper/
# https://dev.to/fernandezpablo/scrappeando-propiedades-con-python-4cp8

"""
Property Scraper: Scrapes property links from various real estate sites and sends new ones via Telegram.
"""
from time import sleep
from typing import List, Dict
import os

# Import from our modules
from scraper import create_scraper, extract_ads, extract_property_details, parse_search_details, test_all_scrapers
from utils import (
    load_environment, load_urls, split_seen_and_unseen, update_history,
    notify_telegram, save_properties_to_csv, format_telegram_message
)


def main():
    """Main function to run the property scraper."""
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
    
    # Create scraper instance
    scraper = create_scraper()
    
    # Store all scraped properties for CSV
    all_properties: List[Dict] = []
    
    # Process each URL
    for url in urls:
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                print(f"Scraping: {url}")
                response = scraper.get(url)
                ads = list(extract_ads(url, response.text))
                
                # Remove duplicates
                ads = [dict(t) for t in {tuple(d.items()) for d in ads}]
                seen, unseen = split_seen_and_unseen(ads, history_fp)
                
                print(f"{len(seen)} seen, {len(unseen)} unseen")
                
                # Process all ads for CSV (both seen and unseen)
                for ad in ads:
                    try:
                        ad_response = scraper.get(ad['url'])
                        property_details = extract_property_details(ad['url'], ad_response.text)
                        all_properties.append(property_details)
                        sleep(1)  # Be respectful to the servers
                    except Exception as e:
                        print(f"Error extracting details from {ad['url']}: {e}")
                
                # Send notifications only for unseen ads
                if unseen:
                    search_details = parse_search_details(url)
                    
                    for ad in unseen:
                        message = format_telegram_message(ad['url'], search_details)
                        success = notify_telegram(env['telegram_bot_id'], env['telegram_id'], message)
                        if success:
                            print(f"Notification sent for: {ad['url']}")
                        else:
                            print(f"Failed to send notification for: {ad['url']}")
                        sleep(1)  # Rate limiting
                    
                    # Update history with new URLs
                    new_urls = [ad['url'] for ad in unseen]
                    update_history(history_fp, new_urls)
                
                break  # Success, exit retry loop
                
            except Exception as e:
                retry_count += 1
                print(f"Error scraping {url} (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    sleep(5)  # Wait before retry
                else:
                    print(f"Failed to scrape {url} after {max_retries} attempts")
    
    # Save all properties to CSV
    if all_properties:
        save_properties_to_csv(all_properties, csv_filename)
        print(f"Scraped {len(all_properties)} total properties")
    
    print("Scraping completed!")


if __name__ == "__main__":
    # Test scrapers (comment out when running main workflow)
    # test_all_scrapers()
    
    # Run main workflow
    main()
