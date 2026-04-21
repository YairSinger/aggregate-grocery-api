import os
import time
from typing import List
from playwright.sync_api import sync_playwright
from app.pipeline.base_scraper import ScraperBase

class ShufersalScraper(ScraperBase):
    def __init__(self, download_dir: str = "downloads"):
        super().__init__("Shufersal", download_dir)
        self.url = "https://prices.shufersal.co.il/"

    def fetch_store_list(self) -> List[str]:
        # Shufersal doesn't provide a clean store file in the same way, 
        # but we can grab one if it's available in the list.
        return self._fetch_via_playwright(store_ids=["134"], category="0", file_types=["Stores"])

    def fetch_prices(self, store_ids: List[str]) -> List[str]:
        downloaded = []
        # Category 2 = PricesFull
        downloaded.extend(self._fetch_via_playwright(store_ids=store_ids, category="2", file_types=["PriceFull"]))
        # Category 4 = PromosFull
        downloaded.extend(self._fetch_via_playwright(store_ids=store_ids, category="4", file_types=["PromoFull"]))
        return downloaded

    def _fetch_via_playwright(self, store_ids: List[str], category: str = "0", file_types: List[str] = []) -> List[str]:
        downloaded = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=True, 
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            page.goto(self.url, timeout=60000)
            page.wait_for_load_state("networkidle")

            for store_id in store_ids:
                print(f"  Selecting Shufersal Store {store_id} in category {category}...")
                try:
                    # Select store and wait
                    page.select_option("select#ddlStore", value=store_id)
                    time.sleep(3)
                    
                    # Select category and wait
                    page.select_option("select#ddlCategory", value=category)
                    time.sleep(7) # Wait for AJAX table refresh
                    
                    # Verify if table has links
                    links = page.query_selector_all("a")
                    # We look for links that have 'blob.core.windows.net' to be sure they are data links
                    download_links = [l for l in links if "blob.core.windows.net" in (l.get_attribute("href") or "")]
                    print(f"    Found {len(download_links)} total data links.")
                    
                    for link in download_links:
                        href = link.get_attribute("href") or ""
                        text = link.inner_text() or ""
                        
                        # Filter by file types if specified
                        if file_types and not any(t in href for t in file_types):
                            continue
                            
                        # Extract a nice filename from the URL or text
                        import re
                        match = re.search(r"(PriceFull|Price|PromoFull|Promo|Stores)[^?]*", href)
                        basename = match.group(0) if match else f"data_{int(time.time())}"
                        
                        filename = f"Shufersal_{store_id}_{basename}.gz" if not basename.endswith(".gz") else f"Shufersal_{store_id}_{basename}"
                        
                        if not self._is_download_needed(filename):
                            downloaded.append(os.path.join(self.download_dir, filename))
                            continue

                        try:
                            with page.expect_download(timeout=60000) as download_info:
                                link.click()
                            download = download_info.value
                            dest = os.path.join(self.download_dir, filename)
                            download.save_as(dest)
                            downloaded.append(dest)
                            print(f"      Downloaded: {filename}")
                        except Exception as download_err:
                            print(f"      Download failed: {download_err}")
                except Exception as e:
                    print(f"    Failed for {store_id}: {e}")
            
            browser.close()
        return downloaded
