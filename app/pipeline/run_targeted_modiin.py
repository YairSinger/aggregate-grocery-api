import os
import time
from playwright.sync_api import sync_playwright
from typing import List

# Highly Targeted Modiin Store IDs
TARGETS = {
    "Shufersal": ["119", "134", "489"],
    "RamiLevy": ["101", "102"],
    "Victory": ["201"],
    "Yohananof": ["34"] # Tishrei St
}

class TargetedModiinScraper:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)

    def scrape_shufersal(self, page):
        print("--- Scraping Shufersal (Modiin) ---")
        page.goto("https://prices.shufersal.co.il/", timeout=60000)
        page.wait_for_load_state("networkidle")
        
        for sid in TARGETS["Shufersal"]:
            print(f"  Targeting Store {sid}...")
            try:
                page.select_option("select#ddlStore", value=sid)
                time.sleep(2)
                page.select_option("select#ddlCategory", value="0") # All
                time.sleep(5)
                
                # Download PriceFull and PromoFull
                links = page.query_selector_all("a:has-text('Download')")
                count = 0
                for link in links:
                    text = link.inner_text()
                    if any(t in text for t in ["PriceFull", "PromoFull", "Stores"]):
                        with page.expect_download(timeout=60000) as download_info:
                            link.click()
                        download = download_info.value
                        dest = os.path.join(self.download_dir, f"Shufersal_{sid}_{download.suggested_filename}")
                        download.save_as(dest)
                        print(f"    Downloaded: {os.path.basename(dest)}")
                        count += 1
                    if count >= 3: break
            except Exception as e:
                print(f"    Failed for {sid}: {e}")

    def scrape_cerberus(self, page, name, url):
        print(f"--- Scraping {name} (Modiin) ---")
        page.goto(url, timeout=60000)
        
        # Login handshake
        try:
            page.click("input[type='submit'][value='כניסה']", timeout=10000)
            page.wait_for_load_state("networkidle")
            time.sleep(5)
        except: pass

        # Find files for our target IDs
        target_ids = TARGETS.get(name, [])
        frames = page.frames
        downloaded_count = 0
        
        for frame in frames:
            links = frame.query_selector_all("a")
            for link in links:
                text = link.inner_text() or ""
                # Check if it matches any of our Modiin branch IDs
                if any(f"-{bid}-" in text or f"-{bid.zfill(3)}-" in text for bid in target_ids) or "Stores" in text:
                    if any(t in text for t in ["PriceFull", "PromoFull", "Stores"]):
                        try:
                            with page.expect_download(timeout=60000) as download_info:
                                link.click()
                            download = download_info.value
                            dest = os.path.join(self.download_dir, f"{name}_{download.suggested_filename}")
                            download.save_as(dest)
                            print(f"    Downloaded: {os.path.basename(dest)}")
                            downloaded_count += 1
                        except: pass
            if downloaded_count >= 10: break

    def run(self):
        with sync_playwright() as p:
            # Using non-headless if needed, but headless should work with stealthy headers
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=True,
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            self.scrape_shufersal(page)
            
            cerberus_chains = {
                "RamiLevy": "https://url.retail.publishedprices.co.il/login/user/RamiLevi",
                "Victory": "https://url.retail.publishedprices.co.il/login/user/Victory",
                "Yohananof": "https://url.retail.publishedprices.co.il/login/user/yohananof"
            }
            
            for name, url in cerberus_chains.items():
                self.scrape_cerberus(page, name, url)
                
            browser.close()

if __name__ == "__main__":
    scraper = TargetedModiinScraper()
    scraper.run()
