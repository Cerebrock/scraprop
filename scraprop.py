import os
import random
from dataclasses import dataclass
from hashlib import sha1
from time import sleep
from urllib.parse import urlparse, urljoin
import re
import cloudscraper
import requests
from bs4 import BeautifulSoup
from lxml import html

wd = "/home/cerebrock/MyStuff/Programas Varios/scraprop/"
telegram_bot_id = ""
telegram_uid = ""
    
# https://pypi.org/project/cloudscraper/
# https://dev.to/fernandezpablo/scrappeando-propiedades-con-python-4cp8

urls = [
    #    "https://www.argenprop.com/departamento-alquiler-barrio-chacarita-hasta-25000-pesos-orden-masnuevos",
    "https://www.facebook.com/marketplace/buenosaires/propertyrentals?minPrice=30000&maxPrice=80000&isC2CListingOnly=1&minAreaSize=50&sortBy=creation_time_descend&exact=false&latitude=-34.5843&longitude=-58.4916&radius=8",
    "https://www.zonaprop.com.ar/departamentos-alquiler-capital-federal-mas-50-m2-35000-80000-pesos-orden-antiguedad-ascendente.html",
    "https://inmuebles.mercadolibre.com.ar/departamentos/alquiler/capital-federal/_PriceRange_45000ARS-80000ARS_NoIndex_True_TOTAL*AREA_50-*#applied_filter_id%3DTOTAL_AREA%26applied_filter_name%3DSuperficie+total%26applied_filter_order%3D9%26applied_value_id%3D50-*%26applied_value_name%3D50-*%26applied_value_order%3D5%26applied_value_results%3DUNKNOWN_RESULTS%26is_custom%3Dtrue",
    "https://www.zonaprop.com.ar/departamentos-alquiler-vicente-lopez-mas-50-m2-35000-80000-pesos-orden-antiguedad-ascendente.html",
]

# random.shuffle(urls)

# href="/marketplace/item/433974314851567/
# dom = html.fromstring(res.text)
# imgs = [l.replace('\\', '') for l in re.findall(img_pattern, contents)]


@dataclass
class Parser:
    website: str
    link_pattern: str = ""
    use_regex: bool = False

    def extract_links(self, contents: str):
        soup = BeautifulSoup(contents, "lxml")
        if not self.use_regex:
            ads = soup.select(self.link_pattern)
        else:
            ads = [
                {"href": f"{id_}"} for id_ in re.findall(self.link_pattern, contents)
            ]
        for ad in ads:
            parsed = urlparse(ad["href"])
            if parsed.hostname is None:
                url = self.website.rstrip("/") + f"/{parsed.path.lstrip('/')}"
            else:
                url = f"{parsed.scheme}://{parsed.hostname}{parsed.path}"
            # _id = sha1(href.encode("utf-8")).hexdigest()
            yield {"url": url}


parsers = [
    Parser(
        website="https://www.facebook.com/marketplace/item",
        use_regex=True,
        link_pattern='"GroupCommerceProductItem","id":"(\d+?)","primary_listing_photo"',
    ),
    Parser(website="https://www.zonaprop.com.ar", link_pattern="a.go-to-posting"),
    Parser(
        website="https://www.argenprop.com",
        link_pattern="div.listing__items div.listing__item a",
    ),
    Parser(
        website="https://inmuebles.mercadolibre.com.ar",
        link_pattern="li.ui-search-layout__item a.ui-search-link",
    ),
]


def extract_ads(url, text):
    uri = urlparse(url)
    parser = next(p for p in parsers if uri.hostname in p.website)
    return parser.extract_links(text)


def split_seen_and_unseen(ads, history_fp: str):
    history = get_history(history_fp)
    seen = [a for a in ads if a["url"] in history]
    unseen = [a for a in ads if a["url"] not in history]
    return seen, unseen


def get_history(history_fp: str):
    try:
        with open(history_fp, "r") as f:
            return {l.rstrip() for l in f.readlines()}
    except:
        return set()


def notify(ad):
    url = "https://api.telegram.org/bot{}/sendMessage?chat_id={}&text={}".format(
        telegram_bot_id, telegram_uid, ad["url"]
    )
    r = requests.get(url)


def mark_as_seen(unseen, history_fp: str):
    with open(history_fp, "a+") as f:
        ids = ["{}\n".format(u["url"]) for u in unseen]
        f.writelines(ids)


# re.findall('"image":{"uri":"(.+?)"', contents)[0].replace('\\', '')
def _main():
    scraper = cloudscraper.create_scraper()
    history_fp = os.path.join(wd, "seen.txt")
    for url in urls:
        c = 0
        while True:
            try:
                print(url)
                res = scraper.get(url)
                ads = list(extract_ads(url, res.text))
                # remove duplicates
                ads = [dict(t) for t in {tuple(d.items()) for d in ads}]
                seen, unseen = split_seen_and_unseen(ads, history_fp)

                print("{} seen, {} unseen".format(len(seen), len(unseen)))

                for u in unseen:
                    notify(u)

                mark_as_seen(unseen, history_fp)
                break
            except Exception as e:
                print(e)
                c += 1
                sleep(10)
                pass
            if c == 10:
                print("Failed to get {}".format(url))
                break


if __name__ == "__main__":
    _main()


##### 


# to extract images from facebook html        
# dom = html.fromstring(res.text)
# imgs = [l.replace('\\', '') for l in re.findall(img_pattern, contents)]
# ads = [{'href':u, 'img':i} for u,i in zip(ads, imgs)]

# for GraphQL 
class FBParser():
    def extract_links(self):
        headers = {
            'authority': 'www.facebook.com',
            'sec-ch-ua-mobile': '?1',
            'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.71 Mobile Safari/537.36',
            'viewport-width': '714',
            'x-fb-friendly-name': 'MarketplaceRealEstateContentQuery',
            'x-fb-lsd': 'AVp1ixyY1FA',
            'content-type': 'application/x-www-form-urlencoded',
            'sec-ch-ua-platform': '"Android"',
            'accept': '*/*',
            'origin': 'https://www.facebook.com',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'referer': 'https://www.facebook.com/marketplace/buenosaires/propertyrentals?minPrice=30000&maxPrice=80000&isC2CListingOnly=1&minAreaSize=50&sortBy=creation_time_descend&exact=false&latitude=-34.6095&longitude=-58.4205&radius=51',
            'accept-language': 'en-US,en;q=0.9',
        }

        data = {
        'fb_api_caller_class': 'RelayModern',
        'fb_api_req_friendly_name': 'MarketplaceRealEstateContentQuery',
        'variables': '{"buyLocation":{"latitude":-34.6098,"longitude":-58.4198},"categoryIDArray":[1468271819871448],"count":24,"cursor":null,"filterSortingParams":{"sort_by_filter":"CREATION_TIME","sort_order":"DESCEND"},"marketplaceBrowseContext":"CATEGORY_FEED","numericVerticalFields":[{"name":"is_c2c_listing_only","value":1}],"numericVerticalFieldsBetween":[{"max":2147483647,"min":50,"name":"area_size"}],"priceRange":[3000000,8000000],"radius":13000,"savedSearchID":"","scale":1,"stringVerticalFields":[],"topicPageParams":{"location_id":"buenosaires","url":"propertyrentals"}}',
        'server_timestamps': 'true',
        'doc_id': '4713178878720143'
        }

        response = requests.post('https://www.facebook.com/api/graphql/', headers=headers, data=data)
        js = response.json()
        item_ids = [l['node']['listing']['id'] for l in js['data']['viewer']['marketplace_feed_stories']['edges']]
        for item_id in item_ids:
            yield {"url": f"{self.website}/{item_id}"}
