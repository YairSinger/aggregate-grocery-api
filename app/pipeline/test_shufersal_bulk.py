import requests
import os
from lxml import html
from typing import List, Optional

def get_shufersal_bulk_links():
    """
    Directly fetches the file list from Shufersal's backend controller.
    This bypasses the slow UI dropdowns.
    """
    url = "https://prices.shufersal.co.il/File/GetFiles"
    # Category 5 is 'Stores', 1 is 'PriceFull', 2 is 'PromoFull'
    categories = [5, 1, 2]
    all_links = []
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    })

    for cat in categories:
        print(f"Fetching Shufersal Category {cat}...")
        params = {"category": cat, "storeId": 0} # 0 = All Stores
        try:
            r = session.get(url, params=params, verify=False, timeout=30)
            if r.status_code == 200:
                # Shufersal returns a partial HTML table in the response
                tree = html.fromstring(r.content)
                links = tree.xpath("//a/@href")
                print(f"  Found {len(links)} files in category {cat}")
                # Filter for latest files (optional, but good for bulk)
                all_links.extend(links)
        except Exception as e:
            print(f"  Error: {e}")
            
    return all_links

if __name__ == "__main__":
    links = get_shufersal_bulk_links()
    print(f"Total Shufersal Bulk Links: {len(links)}")
    if links:
        print(f"Sample: {links[0]}")
