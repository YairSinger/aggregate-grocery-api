import os
import time
import requests
from lxml import html
from playwright.sync_api import sync_playwright
from typing import List, Dict

# Verified Modiin Store IDs
MODIIN_IDS = {
    "Shufersal": ["119", "134", "489"],
    "RamiLevy": ["101", "102"],
    "Victory": ["201"]
}

class ModiinBulkFetcher:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        })

    def fetch_shufersal(self):
        """Uses Playwright to extract links for specific Modiin stores."""
        print("--- Fetching Shufersal (Modiin) ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
            page = context.new_page()
            
            page.goto("https://prices.shufersal.co.il/", timeout=60000)
            page.wait_for_load_state("networkidle")
            
            downloaded = []
            for store_id in MODIIN_IDS["Shufersal"]:
                print(f"  Selecting Store {store_id}...")
                try:
                    page.select_option("select#ddlStore", value=store_id)
                    time.sleep(2)
                    page.select_option("select#ddlCategory", value="0") # All
                    time.sleep(4) # Wait for AJAX
                    
                    # Extract links
                    links = page.query_selector_all("a")
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if "Download" in href:
                            # Direct download via browser to get session context
                            try:
                                with page.expect_download(timeout=30000) as download_info:
                                    link.click()
                                download = download_info.value
                                dest = os.path.join(self.download_dir, f"Shufersal_{store_id}_{download.suggested_filename}")
                                download.save_as(dest)
                                downloaded.append(dest)
                                print(f"    Downloaded: {os.path.basename(dest)}")
                                # Get only latest PriceFull and PromoFull
                                if len([d for d in downloaded if store_id in d]) >= 3:
                                    break
                            except: pass
                except Exception as e:
                    print(f"    Failed for {store_id}: {e}")
            browser.close()
        return downloaded

    def fetch_cerberus(self, chain_name: str, username: str):
        """Uses direct Session + CSRF login for Rami Levy/Victory."""
        print(f"--- Fetching {chain_name} (Modiin) ---")
        base_url = "https://url.retail.publishedprices.co.il"
        login_url = f"{base_url}/login/user"
        
        # 1. Get CSRF Token
        r1 = self.session.get(login_url, verify=False)
        tree = html.fromstring(r1.content)
        csrf = tree.xpath("//meta[@name='csrftoken']/@content")
        csrf_token = csrf[0] if csrf else ""
        
        # 2. Login
        login_data = {"username": username, "password": "", "csrftoken": csrf_token}
        r2 = self.session.post(login_url, data=login_data, verify=False)
        
        if "Sign Out" not in r2.text:
            print(f"  Login failed for {chain_name}")
            return []

        # 3. Access file list
        # Cerberus usually shows the list on the root after login
        r3 = self.session.get(base_url, verify=False)
        tree = html.fromstring(r3.content)
        links = tree.xpath("//a[contains(@href, 'Download')]/@href")
        
        downloaded = []
        target_ids = MODIIN_IDS.get(chain_name, [])
        
        for link_path in links:
            # Filename is usually part of the link text or title
            # In Cerberus, the link text is the filename
            filename = tree.xpath(f"//a[@href='{link_path}']/text()")[0].strip()
            
            # Filter for Modiin IDs and latest files
            if any(f"-{bid}-" in filename or f"-{bid.zfill(3)}-" in filename for bid in target_ids):
                if any(t in filename for t in ["PriceFull", "PromoFull", "Stores"]):
                    print(f"  Downloading {filename}...")
                    full_url = f"{base_url}{link_path}"
                    try:
                        r_file = self.session.get(full_url, verify=False, stream=True)
                        dest = os.path.join(self.download_dir, f"{chain_name}_{filename}")
                        with open(dest, "wb") as f:
                            for chunk in r_file.iter_content(chunk_size=8192):
                                f.write(chunk)
                        downloaded.append(dest)
                    except Exception as e:
                        print(f"    Failed: {e}")
            
            # Limit to stay under 10GB (though Modiin only will never hit it)
            if len(downloaded) >= 20: break
            
        return downloaded

    def run_all(self):
        results = {}
        # Shufersal still needs browser for its complex AJAX
        results["Shufersal"] = self.fetch_shufersal()
        # Cerberus chains can be done via direct requests (much faster)
        results["RamiLevy"] = self.fetch_cerberus("RamiLevy", "RamiLevi")
        results["Victory"] = self.fetch_cerberus("Victory", "Victory")
        return results

if __name__ == "__main__":
    fetcher = ModiinBulkFetcher()
    fetcher.run_all()
