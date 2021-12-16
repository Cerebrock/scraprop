# latitude=-34.6123&longitude=-58.4428
import requests

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
