import os
import requests
import time
from typing import List, Optional, Dict
from lxml import html
from urllib3.exceptions import InsecureRequestWarning

# Suppress insecure request warnings for portals with bad SSL
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

class ChainDownloader:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        })

    def _get_links(self, url: str) -> List[str]:
        try:
            response = self.session.get(url, verify=False, timeout=30)
            response.raise_for_status()
            tree = html.fromstring(response.content)
            return [l for l in tree.xpath('//a/@href') if l]
        except Exception as e:
            print(f"Error fetching links from {url}: {e}")
            return []

    def download_file(self, url: str, chain_name: str) -> Optional[str]:
        try:
            # Handle relative URLs if any
            if url.startswith('/'):
                # This is a bit simplified, usually needs base URL
                return None
            
            file_name = url.split('/')[-1].split('?')[0]
            if not file_name.endswith(('.gz', '.xml')):
                file_name += ".gz"
            
            dest_path = os.path.join(self.download_dir, f"{chain_name}_{file_name}")
            
            print(f"Downloading {file_name} from {chain_name}...")
            with self.session.get(url, stream=True, verify=False, timeout=60) as r:
                r.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
            return dest_path
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None

    def download_shufersal(self) -> List[str]:
        """Specific logic for Shufersal's portal."""
        url = "https://prices.shufersal.co.il/"
        links = self._get_links(url)
        # Shufersal usually has 'PriceFull' and 'PromoFull' in the filename
        # We look for the most recent ones
        targets = []
        for t in ["PriceFull", "PromoFull", "Stores"]:
            matches = [l for l in links if t in l]
            if matches:
                # Get the most recent (usually sorted by name/date on the portal)
                latest = sorted(matches, reverse=True)[0]
                full_url = latest if latest.startswith('http') else f"{url.rstrip('/')}/{latest.lstrip('/')}"
                path = self.download_file(full_url, "Shufersal")
                if path: targets.append(path)
        return targets

    def get_chain_files(self, url: str, chain_name: str, city_filter: str = None) -> List[str]:
        """
        Generic flow: 
        1. Find Stores file -> Download
        2. (Future) Find Modi'in Store IDs
        3. Find PriceFull/PromoFull for those IDs
        """
        links = self._get_links(url)
        downloaded = []
        
        # 1. Always get the latest Stores file first
        stores_link = next((l for l in links if "Stores" in l), None)
        if stores_link:
            # If relative path
            full_stores_url = stores_link if stores_link.startswith('http') else f"{url.rstrip('/')}/{stores_link.lstrip('/')}"
            path = self.download_file(full_stores_url, chain_name)
            if path: downloaded.append(path)

        # 2. Get PriceFull and PromoFull (Limit to first 2 for MVP/Testing)
        target_types = ["PriceFull", "PromoFull"]
        for t in target_types:
            link = next((l for l in links if t in l), None)
            if link:
                full_url = link if link.startswith('http') else f"{url.rstrip('/')}/{link.lstrip('/')}"
                path = self.download_file(full_url, chain_name)
                if path: downloaded.append(path)
                
        return downloaded

    def download_all_chains(self) -> Dict[str, List[str]]:
        chains = {
            "Shufersal": "https://prices.shufersal.co.il/",
            "RamiLevy": "http://prices.rami-levy.co.il/",
            "Victory": "http://prices.victory.co.il/",
            "Yohananof": "http://publishprice.yohananof.co.il/",
        }
        
        results = {}
        for name, url in chains.items():
            print(f"--- Scraping {name} ---")
            results[name] = self.get_chain_files(url, name)
            time.sleep(1) # Be polite
        return results
