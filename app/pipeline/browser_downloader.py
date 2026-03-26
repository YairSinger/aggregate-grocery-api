import os
import time
from playwright.sync_api import sync_playwright
from typing import List, Dict

class BrowserDownloader:
    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)

    def scrape_shufersal(self, page) -> List[str]:
        print("Scraping Shufersal (Modiin Branches)...")
        page.goto("https://prices.shufersal.co.il/", timeout=60000)
        page.wait_for_load_state("networkidle")
        
        # Select Modiin Ishpro (134) or similar to get specific files
        # 134 = יוניברס מודיעין- ישפרו סנטר
        try:
            page.select_option("select#ddlStore", value="134")
            time.sleep(3)
            # Category 0 = All (to get Price + Promo + Stores)
            page.select_option("select#ddlCategory", value="0")
            time.sleep(5)
        except Exception as e:
            print(f"  Selection failed: {e}")

        downloaded = []
        # Wait for the table to contain 'Download'
        try:
            page.wait_for_selector("a:has-text('Download')", timeout=10000)
        except:
            print("  Table did not populate with 'Download' links in time.")

        links = page.query_selector_all("a")
        count = 0
        for link in links:
            href = link.get_attribute("href") or ""
            if "Download" in href:
                try:
                    with page.expect_download(timeout=60000) as download_info:
                        link.click()
                    download = download_info.value
                    dest = os.path.join(self.download_dir, f"Shufersal_134_{download.suggested_filename}")
                    download.save_as(dest)
                    downloaded.append(dest)
                    print(f"    Downloaded: {os.path.basename(dest)}")
                    count += 1
                except: pass
            if count >= 5: break
        return downloaded

    def scrape_cerberus(self, page, url: str, chain_name: str) -> List[str]:
        print(f"Scraping {chain_name} (Bulk)...")
        page.goto(url, timeout=60000)
        
        # 1. Click 'Login' or 'Enter'
        try:
            page.click("input[type='submit'][value='כניסה']", timeout=10000)
            page.wait_for_load_state("networkidle")
            time.sleep(5)
        except:
            print(f"  No login button found for {chain_name}, proceeding.")

        # 2. Look for files in frames
        downloaded = []
        frames = page.frames
        for frame in frames:
            links = frame.query_selector_all("a")
            for link in links:
                text = link.inner_text() or ""
                # Filter for Modiin branch IDs if possible, or just latest
                # For Rami Levy, branch 101 or similar is often Modiin
                if any(t in text for t in ["PriceFull", "PromoFull", "Stores"]):
                    try:
                        with page.expect_download(timeout=60000) as download_info:
                            link.click()
                        download = download_info.value
                        dest = os.path.join(self.download_dir, f"{chain_name}_{download.suggested_filename}")
                        download.save_as(dest)
                        downloaded.append(dest)
                        print(f"    Downloaded {chain_name}: {os.path.basename(dest)}")
                        if len(downloaded) >= 10: break
                    except: pass
            if len(downloaded) >= 10: break
        return downloaded

    def scrape_all(self):
        with sync_playwright() as p:
            # Using browser with a real user agent
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                accept_downloads=True, 
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            results = {}
            results["Shufersal"] = self.scrape_shufersal(page)
            
            chains = {
                "RamiLevy": "https://url.retail.publishedprices.co.il/login/user/RamiLevi",
                "Victory": "https://url.retail.publishedprices.co.il/login/user/Victory",
            }
            
            for name, url in chains.items():
                results[name] = self.scrape_cerberus(page, url, name)
                
            browser.close()
            return results

if __name__ == "__main__":
    downloader = BrowserDownloader()
    downloader.scrape_all()
