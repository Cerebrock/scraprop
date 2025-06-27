"""
Property Scraper Module: Contains all scraping-related functionality.
"""
import re
from urllib.parse import urlparse
import cloudscraper
from bs4 import BeautifulSoup


def create_scraper():
    """Create and return a cloudscraper instance."""
    return cloudscraper.create_scraper()


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
        # Zonaprop ad extraction
        for ad in soup.select('.posting-card, .aviso-row'):
            link_tag = ad.select_one('a[href*="/propiedades/"]')
            if link_tag and link_tag.get('href'):
                full_url = link_tag['href']
                if not full_url.startswith('http'):
                    full_url = 'https://www.zonaprop.com.ar' + full_url
                ads.append({'url': full_url})
                
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

    # --- Zonaprop ---
    if 'zonaprop.com.ar' in url:
        price = neighbourhood = surface = rooms = expenses = None
        # Try to extract from JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'offers' in data and 'price' in data['offers']:
                        price = data['offers']['price']
                    if 'address' in data and 'streetAddress' in data['address']:
                        neighbourhood = data['address']['streetAddress']
                    if 'numberOfRooms' in data:
                        rooms = data['numberOfRooms']
                    if 'floorSize' in data and 'value' in data['floorSize']:
                        surface = f"{data['floorSize']['value']} m²"
                    # Try to extract expenses from JSON-LD (custom fields)
                    if 'additionalProperty' in data:
                        for prop in data['additionalProperty']:
                            if isinstance(prop, dict) and 'name' in prop and 'expensa' in prop['name'].lower():
                                expenses = prop.get('value')
            except Exception:
                pass
        # Fallbacks
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
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms

    # --- MercadoLibre ---
    elif 'mercadolibre.com.ar' in url:
        price = neighbourhood = surface = rooms = expenses = None
        # Try to extract from JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Price
                    if 'offers' in data and 'price' in data['offers']:
                        price = data['offers']['price']
                    # Neighbourhood/address
                    if 'address' in data and 'streetAddress' in data['address']:
                        neighbourhood = data['address']['streetAddress']
                    # Surface
                    if 'floorSize' in data and 'value' in data['floorSize']:
                        surface = f"{data['floorSize']['value']} m²"
                    # Rooms
                    if 'numberOfRooms' in data:
                        rooms = data['numberOfRooms']
            except Exception:
                pass
        # Fallbacks
        if not price:
            price_json = re.search(r'"price":\s*(\d+)', html)
            if price_json:
                price = f"${price_json.group(1)}"
            else:
                price_tag = soup.select_one('.price-tag-fraction, .ui-pdp-price__second-line, .price-tag-symbol, .price-tag, span[class*="price"]')
                price = price_tag.get_text(strip=True) if price_tag else None
        if not neighbourhood:
            neighbourhood_json = re.search(r'"addressLine"\s*:\s*"([^"]+)"', html)
            if neighbourhood_json:
                neighbourhood = neighbourhood_json.group(1)
            else:
                zone_tag = soup.select_one('.ui-vip-location__subtitle, .ui-pdp-media__title, .breadcrumb, [data-testid="address"]')
                neighbourhood = zone_tag.get_text(strip=True) if zone_tag else None
        if not surface:
            # Try JSON
            surface_json = re.search(r'"Superficie total"\s*[:,]\s*"?(\d+\s?m²)"?', html)
            if surface_json:
                surface = surface_json.group(1)
            else:
                # Try table/definition list
                for label in soup.find_all(['th', 'dt'], string=re.compile(r"Superficie", re.IGNORECASE)):
                    value = label.find_next(['td', 'dd'])
                    if value:
                        surface = value.get_text(strip=True)
                        break
                if not surface:
                    surface_tag = soup.find(string=re.compile(r"(\d+\s?m²|\d+\s?m2)"))
                    surface = surface_tag.strip() if surface_tag else None
        if not rooms:
            # Try JSON
            rooms_json = re.search(r'"Ambientes"\s*[:,]\s*"?(\d+)"?', html)
            if rooms_json:
                rooms = rooms_json.group(1)
            else:
                # Try table/definition list
                for label in soup.find_all(['th', 'dt'], string=re.compile(r"Ambientes", re.IGNORECASE)):
                    value = label.find_next(['td', 'dd'])
                    if value:
                        rooms = value.get_text(strip=True)
                        break
                if not rooms:
                    rooms_cell = soup.find('td', string=re.compile(r"Ambientes", re.IGNORECASE))
                    if rooms_cell and rooms_cell.find_next_sibling('td'):
                        rooms = rooms_cell.find_next_sibling('td').get_text(strip=True)
        # Expenses: look for 'expensas' in text
        expensas_tag = soup.find(string=re.compile(r"expensas", re.IGNORECASE))
        if expensas_tag:
            match = re.search(r"\$\s?([\d\.]+)", expensas_tag)
            if match:
                expenses = match.group(1)
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms

    # --- Argenprop ---
    elif 'argenprop.com' in url:
        price = neighbourhood = surface = rooms = expenses = None
        # Try to extract from JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if 'offers' in data and 'price' in data['offers']:
                        price = data['offers']['price']
                    if 'address' in data and 'streetAddress' in data['address']:
                        neighbourhood = data['address']['streetAddress']
                    if 'numberOfRooms' in data:
                        rooms = data['numberOfRooms']
                    if 'floorSize' in data and 'value' in data['floorSize']:
                        surface = f"{data['floorSize']['value']} m²"
                    # Try to extract expenses from JSON-LD (custom fields)
                    if 'additionalProperty' in data:
                        for prop in data['additionalProperty']:
                            if isinstance(prop, dict) and 'name' in prop and 'expensa' in prop['name'].lower():
                                expenses = prop.get('value')
            except Exception:
                pass
        # Fallbacks
        if not price:
            price_tag = soup.select_one('.listing__price, .price, .property-price, [data-qa="price"]')
            price = price_tag.get_text(strip=True) if price_tag else None
        if not neighbourhood:
            zone_tag = soup.select_one('.listing__location, .location, .property-location, [data-qa="location"]')
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
        details['price'] = price
        details['expenses'] = expenses
        details['neighbourhood'] = neighbourhood
        details['surface'] = surface
        details['rooms'] = rooms

    # --- Facebook Marketplace (limited) ---
    elif 'facebook.com' in url:
        details['price'] = None
        details['expenses'] = None
        details['neighbourhood'] = None
        details['surface'] = None
        details['rooms'] = None
    else:
        details['price'] = None
        details['expenses'] = None
        details['neighbourhood'] = None
        details['surface'] = None
        details['rooms'] = None

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