"""
Property Scraper Module: Contains all scraping-related functionality.
"""
import re
from urllib.parse import urlparse
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright
import time


def create_scraper():
    """Create and return a cloudscraper instance."""
    return cloudscraper.create_scraper()


class PlaywrightScraper:
    """Scraper using Playwright for sites that block cloudscraper."""
    
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        
    def get(self, url: str) -> str:
        """Fetch HTML content using Playwright."""
        try:
            self.page.goto(url, wait_until='networkidle')
            time.sleep(2)  # Additional wait for dynamic content
            return self.page.content()
        except Exception as e:
            print(f"Playwright error: {e}")
            return ""
    
    def close(self):
        """Close the browser and playwright."""
        try:
            self.browser.close()
            self.playwright.stop()
        except Exception:
            pass


def parse_search_details(url):
    """Extract zone, price, and minimum surface from a search URL."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    zone = price = min_surface = None
    
    # Zonaprop
    if 'zonaprop.com.ar' in parsed.netloc:
        # Example: /departamentos-alquiler-capital-federal-mas-50-m2-35000-1000000-pesos-orden-antiguedad-ascendente-q-terraza.html
        # Try to extract zone
        zone_match = re.search(r'alquiler-([a-z\-]+)-mas', path)
        if zone_match:
            zone = zone_match.group(1).replace('-', ' ').title()
        # Try to extract price range
        price_match = re.search(r'(\d+)-(\d+)-pesos', path)
        if price_match:
            price = f"${price_match.group(1)} - ${price_match.group(2)}"
        # Try to extract minimum surface
        surface_match = re.search(r'mas-(\d+)-m2', path)
        if surface_match:
            min_surface = surface_match.group(1)
            
    # Argenprop
    elif 'argenprop.com' in parsed.netloc:
        # Example: /casas-o-departamentos-o-locales-o-ph/alquiler/belgrano-o-br-norte-o-colegiales-o-florida-vicente-lopez-o-palermo-o-parque-centenario-o-saavedra-o-vicente-lopez/pesos-300000-1700000
        # Try to extract zones
        zone_match = re.search(r'alquiler/([^/]+)', path)
        if zone_match:
            zone = zone_match.group(1).replace('-o-', ', ').replace('-', ' ').title()
        # Try to extract price range
        price_match = re.search(r'pesos-(\d+)-(\d+)', path)
        if price_match:
            price = f"${price_match.group(1)} - ${price_match.group(2)}"
            
    # MercadoLibre
    elif 'mercadolibre.com.ar' in parsed.netloc:
        # Extract from query parameters
        query = parsed.query
        fragment = parsed.fragment
        
        # Try to extract price range from fragment or query
        price_match = re.search(r'(\d+)ARS-(\d+)ARS', query + fragment)
        if price_match:
            price = f"${price_match.group(1)} - ${price_match.group(2)}"
        
        # Try to extract minimum surface
        surface_match = re.search(r'AREA_(\d+)-', query + fragment)
        if surface_match:
            min_surface = surface_match.group(1)
            
        # Try to extract zone from path
        zone_match = re.search(r'/([^/]+)/_', path)
        if zone_match:
            zone = zone_match.group(1).replace('-', ' ').title()
    
    return zone, price, min_surface


def extract_ads(url, html):
    """Extract ad URLs from a search result page for all supported sources."""
    soup = BeautifulSoup(html, "lxml")
    ads = []
    
    if 'zonaprop.com.ar' in url:
        # Zonaprop ad extraction - Updated based on debug findings
        # Look for direct property links first
        property_links = soup.find_all('a', href=True)
        for link in property_links:
            href = link.get('href')
            if href and ('/propiedades/' in href or '/propiedad/' in href):
                # Build full URL
                if not href.startswith('http'):
                    full_url = 'https://www.zonaprop.com.ar' + href
                else:
                    full_url = href
                ads.append({'url': full_url})
        
        # Remove duplicates
        unique_ads = []
        seen_urls = set()
        for ad in ads:
            if ad['url'] not in seen_urls:
                unique_ads.append(ad)
                seen_urls.add(ad['url'])
        ads = unique_ads
                
    elif 'mercadolibre.com.ar' in url:
        # MercadoLibre ad extraction
        for ad in soup.select('.ui-search-result, .andes-card'):
            link_tag = ad.select_one('a[href*="/MLA-"]')
            if link_tag and link_tag.get('href'):
                full_url = link_tag['href']
                if not full_url.startswith('http'):
                    full_url = 'https://departamento.mercadolibre.com.ar' + full_url
                ads.append({'url': full_url})
                
    elif 'argenprop.com' in url:
        # Look for property cards with links
        for a in soup.select('a.card__title-link, a.property-title, a.go-to-posting'):  # try common selectors
            href = a.get('href')
            if href and ('/propiedad-' in href or '/departamento-' in href or '/casa-' in href or '/ph-' in href or '/local-' in href):
                if not href.startswith('http'):
                    href = 'https://www.argenprop.com' + href
                ads.append({'url': href})
        # Fallback: look for all links to property pages
        if not ads:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if ('/propiedad-' in href or '/departamento-' in href or '/casa-' in href or '/ph-' in href or '/local-' in href):
                    if not href.startswith('http'):
                        href = 'https://www.argenprop.com' + href
                    ads.append({'url': href})
        # Remove duplicates
        ads = [dict(t) for t in {tuple(d.items()) for d in ads}]
        return ads
                
    elif 'facebook.com' in url:
        # Facebook Marketplace extraction (limited)
        for ad in soup.select('[data-testid="marketplace-item"]'):
            link_tag = ad.select_one('a')
            if link_tag and link_tag.get('href'):
                full_url = link_tag['href']
                if not full_url.startswith('http'):
                    full_url = 'https://www.facebook.com' + full_url
                ads.append({'url': full_url})
    
    return ads


def extract_property_details(url, html):
    """Extract price, expenses, neighbourhood, surface, and other details from a property page."""
    soup = BeautifulSoup(html, "lxml")
    details = {"url": url}
    
    # Add current date as seen_date
    details['seen_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # --- Zonaprop ---
    if 'zonaprop.com.ar' in url:
        price = neighbourhood = surface = rooms = expenses = upload_date = description = None
        
        # Extract description from URL path and Open Graph data
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        url_path = parsed_url.path.lower()
        
        # First try Open Graph meta tags (works even with Cloudflare protection)
        og_title = soup.find('meta', property='og:title')
        og_description = soup.find('meta', property='og:description')
        
        if og_title and og_description:
            title_text = og_title.get('content', '')
            desc_text = og_description.get('content', '')
            combined_text = f"{title_text} {desc_text}"
            
            # Create comprehensive description from URL path + Open Graph data
            description = f"{url_path} {title_text} {desc_text}"
            
            # Extract price from OG data
            price_match = re.search(r'\$\s?([\d.]+)', combined_text)
            if price_match:
                price = f"${price_match.group(1)}"
            
            # Extract surface from OG data
            surface_match = re.search(r'(\d+)\s*m[²2]', combined_text)
            if surface_match:
                surface = f"{surface_match.group(1)} m²"
            
            # Extract rooms from OG data
            rooms_match = re.search(r'(\d+)\s*(amb|ambiente)', combined_text)
            if rooms_match:
                rooms = rooms_match.group(1)
            
            # Extract neighbourhood from OG data
            location_match = re.search(r'en\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', combined_text)
            if location_match:
                neighbourhood = location_match.group(1)
        
        # Try to extract from JSON-LD if OG didn't work
        if not price or not neighbourhood or not surface:
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if not price and 'offers' in data and 'price' in data['offers']:
                            price = data['offers']['price']
                        if not neighbourhood and 'address' in data and 'streetAddress' in data['address']:
                            neighbourhood = data['address']['streetAddress']
                        if not rooms and 'numberOfRooms' in data:
                            rooms = data['numberOfRooms']
                        if not surface and 'floorSize' in data and 'value' in data['floorSize']:
                            surface = f"{data['floorSize']['value']} m²"
                        # Try to extract expenses from JSON-LD (custom fields)
                        if 'additionalProperty' in data:
                            for prop in data['additionalProperty']:
                                if isinstance(prop, dict) and 'name' in prop and 'expensa' in prop['name'].lower():
                                    expenses = prop.get('value')
                        # Try to extract date from JSON-LD
                        if 'datePublished' in data:
                            upload_date = data['datePublished']
                        elif 'dateCreated' in data:
                            upload_date = data['dateCreated']
                except Exception:
                    pass
        
        # Final fallbacks for regular HTML parsing
        if not price:
            price_tag = soup.select_one('.price-value, .price__fraction, .posting-price, .price, [data-qa="POSTING_CARD_PRICE"]')
            price = price_tag.get_text(strip=True) if price_tag else None
        if not neighbourhood:
            zone_tag = soup.select_one('.title-location, .posting-location, .location, [data-qa="POSTING_CARD_LOCATION"]')
            neighbourhood = zone_tag.get_text(strip=True) if zone_tag else None
        if not surface:
            surface_tag = soup.find(string=re.compile(r"(\d+\s?m²|\d+\s?m2)"))
            surface = surface_tag.strip() if surface_tag else None
        if not rooms:
            rooms_tag = soup.find(string=re.compile(r"(\d+)\s*(amb|ambiente)"))
            if rooms_tag:
                match = re.search(r"(\d+)", rooms_tag)
                rooms = match.group(1) if match else None
        # Expenses fallback: look for 'expensas' in text
        if not expenses:
            expensas_tag = soup.find(string=re.compile(r"expensas", re.IGNORECASE))
            if expensas_tag:
                match = re.search(r"\$\s?([\d\.]+)", expensas_tag)
                if match:
                    expenses = match.group(1)
        # Upload date fallback - look for "Publicado hace X días"
        if not upload_date:
            date_match = re.search(r"Publicado hace (\d+) días?", html)
            if date_match:
                upload_date = f"Hace {date_match.group(1)} días"
        
        # If no description was extracted from OG data, use URL path as description
        if not description:
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            description = parsed_url.path.lower()
        
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms
        details['upload_date'] = upload_date
        details['description'] = description

    # --- MercadoLibre ---
    elif 'mercadolibre.com.ar' in url:
        price = neighbourhood = surface = rooms = expenses = upload_date = description = None
        
        # Extract description from URL path
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        url_path = parsed_url.path.lower()
        description = url_path
        
        # Try to extract from the large JSON structure in the page
        # Extract surface directly
        surface_match = re.search(r'"id":"Superficie total","text":"(\d+\s*m²)"', html)
        if surface_match:
            surface = surface_match.group(1)
            
        # Extract rooms directly
        rooms_match = re.search(r'"id":"Ambientes","text":"(\d+)"', html)
        if rooms_match:
            rooms = rooms_match.group(1)
            
        # Extract expenses directly
        expenses_match = re.search(r'"id":"Expensas","text":"([^"]+)"', html)
        if expenses_match:
            expenses_text = expenses_match.group(1)
            if expenses_text != "0 ARS":
                expenses = f"${expenses_text.replace(' ARS', '')}"
        
        # Alternative extraction from highlighted specs
        if not surface or not rooms:
            # Try highlighted specs pattern
            highlighted_match = re.search(r'"highlighted_specs_res".*?"attributes":\[(.*?)\]', html, re.DOTALL)
            if highlighted_match:
                specs_text = highlighted_match.group(1)
                if not surface:
                    surface_match = re.search(r'"text":"(\d+\s*m²)\s*totales"', specs_text)
                    if surface_match:
                        surface = surface_match.group(1)
                if not rooms:
                    # Look for dormitorios (bedrooms) and add 1 for living room
                    bedrooms_match = re.search(r'"text":"(\d+)\s*dormitorios?"', specs_text)
                    if bedrooms_match:
                        bedrooms = int(bedrooms_match.group(1))
                        rooms = str(bedrooms + 1)  # Add 1 for living room
        
        # Extract price from the JSON
        price_match = re.search(r'"price":\{"type":"price","value":(\d+)', html)
        if price_match:
            price_value = int(price_match.group(1))
            price = f"${price_value:,}".replace(",", ".")
        
        # Extract neighbourhood from location
        location_match = re.search(r'"content_rows":\[.*?"title":\{"text":"([^"]+)"', html)
        if location_match:
            full_address = location_match.group(1)
            # Extract neighbourhood from full address (e.g., "Villa Martelli" from "Ameghino Al 700, Villa Martelli, Vicente López, Bs.As. G.B.A. Norte")
            parts = full_address.split(", ")
            if len(parts) >= 2:
                neighbourhood = parts[1]  # Second part is usually the neighbourhood
                
        # Try to extract from JSON-LD as fallback
        if not (price and neighbourhood and surface and rooms):
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Price
                        if not price and 'offers' in data and 'price' in data['offers']:
                            price = f"${data['offers']['price']:,}".replace(",", ".")
                        # Neighbourhood/address
                        if not neighbourhood and 'address' in data:
                            if 'streetAddress' in data['address']:
                                neighbourhood = data['address']['streetAddress']
                            elif 'name' in data['address']:
                                neighbourhood = data['address']['name']
                        # Surface
                        if not surface and 'floorSize' in data and 'value' in data['floorSize']:
                            surface = f"{data['floorSize']['value']} m²"
                        # Rooms
                        if not rooms and 'numberOfRooms' in data:
                            rooms = data['numberOfRooms']
                except Exception:
                    pass
                    
        # Upload date - look for "Publicado hace X días"
        if not upload_date:
            date_match = re.search(r"Publicado hace (\d+) días?", html)
            if date_match:
                upload_date = f"Hace {date_match.group(1)} días"
                
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms
        details['upload_date'] = upload_date
        details['description'] = description

    # --- Argenprop ---
    elif 'argenprop.com' in url:
        price = neighbourhood = surface = rooms = expenses = upload_date = description = None
        
        # Extract description from URL path
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        url_path = parsed_url.path.lower()
        description = url_path
        # Try to extract from JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'offers' in data and 'price' in data['offers']:
                        price_value = data['offers']['price']
                        if isinstance(price_value, (int, float)):
                            price = f"${int(price_value):,}".replace(",", ".")
                        else:
                            price = price_value
                    if 'address' in data:
                        if 'streetAddress' in data['address']:
                            neighbourhood = data['address']['streetAddress']
                        elif 'name' in data['address']:
                            neighbourhood = data['address']['name']
                    if 'numberOfRooms' in data:
                        rooms = data['numberOfRooms']
                    if 'floorSize' in data and 'value' in data['floorSize']:
                        surface = f"{data['floorSize']['value']} m²"
                    # Try to extract expenses from JSON-LD (custom fields)
                    if 'additionalProperty' in data:
                        for prop in data['additionalProperty']:
                            if isinstance(prop, dict) and 'name' in prop and 'expensa' in prop['name'].lower():
                                expenses = prop.get('value')
                    # Try to extract date from JSON-LD
                    if 'datePublished' in data:
                        upload_date = data['datePublished']
                    elif 'dateCreated' in data:
                        upload_date = data['dateCreated']
            except Exception:
                pass
        # Fallbacks
        if not price:
            # Try multiple selectors for price
            price_selectors = [
                '.titlebar__price',
                '.price-value',
                '.property-price__value',
                '[class*="price"] span',
                'span[class*="price"]'
            ]
            for selector in price_selectors:
                price_tag = soup.select_one(selector)
                if price_tag:
                    price_text = price_tag.get_text(strip=True)
                    # Extract numeric value
                    price_match = re.search(r'([\d.]+)', price_text.replace('.', ''))
                    if price_match:
                        price_value = int(price_match.group(1))
                        price = f"${price_value:,}".replace(",", ".")
                        break
        if not neighbourhood:
            # Try multiple selectors
            location_selectors = [
                '.titlebar__address',
                '.property-location',
                '.location__address',
                '[class*="location"] [class*="address"]'
            ]
            for selector in location_selectors:
                zone_tag = soup.select_one(selector)
                if zone_tag:
                    neighbourhood = zone_tag.get_text(strip=True)
                    break
        if not surface:
            # Look for surface in features
            surface_match = soup.find(string=re.compile(r"(\d+)\s*(m²|m2|metros)", re.IGNORECASE))
            if surface_match:
                match = re.search(r"(\d+)\s*(m²|m2|metros)", surface_match, re.IGNORECASE)
                if match:
                    surface = f"{match.group(1)} m²"
        if not rooms:
            # Look for rooms/ambientes
            rooms_match = soup.find(string=re.compile(r"(\d+)\s*(amb|ambiente|ambientes)", re.IGNORECASE))
            if rooms_match:
                match = re.search(r"(\d+)\s*(amb|ambiente|ambientes)", rooms_match, re.IGNORECASE)
                if match:
                    rooms = match.group(1)
        # Expenses fallback: look for 'expensas' in text
        if not expenses:
            expensas_match = soup.find(string=re.compile(r"expensas?\s*:?\s*\$?\s*([\d.]+)", re.IGNORECASE))
            if expensas_match:
                match = re.search(r"expensas?\s*:?\s*\$?\s*([\d.]+)", expensas_match, re.IGNORECASE)
                if match:
                    expenses = f"${match.group(1)}"
        # Upload date fallback
        if not upload_date:
            date_match = re.search(r"Publicado hace (\d+) días?", html)
            if date_match:
                upload_date = f"Hace {date_match.group(1)} días"
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms
        details['upload_date'] = upload_date
        details['description'] = description

    # --- Facebook Marketplace (limited) ---
    elif 'facebook.com' in url:
        details['price'] = None
        details['expenses'] = None
        details['neighbourhood'] = None
        details['surface'] = None
        details['rooms'] = None
        details['upload_date'] = None
        details['description'] = None
    else:
        details['price'] = None
        details['expenses'] = None
        details['neighbourhood'] = None
        details['surface'] = None
        details['rooms'] = None
        details['upload_date'] = None
        details['description'] = None

    return details


def test_zonaprop_scraper():
    """Test scraping a Zonaprop property."""
    url = "https://www.zonaprop.com.ar/propiedades/departamento-2-ambientes-a-estrenar-apto-48706499.html"
    scraper = create_scraper()
    print(f"\n=== Testing Zonaprop scraper ===")
    print(f"URL: {url}")
    try:
        res = scraper.get(url)
        details = extract_property_details(url, res.text)
        print("Extracted details:")
        for k, v in details.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")


def test_mercadolibre_scraper():
    """Test scraping a MercadoLibre property."""
    url = "https://departamento.mercadolibre.com.ar/MLA-2091232812-excelente-3-amb-flores-ver-descripcion-_JM"
    scraper = create_scraper()
    print(f"\n=== Testing MercadoLibre scraper ===")
    print(f"URL: {url}")
    try:
        res = scraper.get(url)
        details = extract_property_details(url, res.text)
        print("Extracted details:")
        for k, v in details.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")


def test_argenprop_scraper():
    """Test scraping an Argenprop property."""
    url = "https://www.argenprop.com/departamento-en-alquiler-en-las-canitas-3-ambientes--11177163"
    scraper = create_scraper()
    print(f"\n=== Testing Argenprop scraper ===")
    print(f"URL: {url}")
    try:
        res = scraper.get(url)
        details = extract_property_details(url, res.text)
        print("Extracted details:")
        for k, v in details.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")


def test_all_scrapers():
    """Test all property scrapers."""
    print("Testing all property scrapers...")
    test_zonaprop_scraper()
    test_mercadolibre_scraper()
    test_argenprop_scraper()
    print("\n=== All tests completed ===")


if __name__ == "__main__":
    # Run tests when module is executed directly
    test_all_scrapers() 