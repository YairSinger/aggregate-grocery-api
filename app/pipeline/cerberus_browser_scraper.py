import os
import time
from typing import List
from playwright.sync_api import sync_playwright
from app.pipeline.base_scraper import ScraperBase

class CerberusBrowserScraper(ScraperBase):
    def __init__(self, chain_name: str, username: str, download_dir: str = "downloads"):
        super().__init__(chain_name, download_dir)
        self.username = username
        self.url = "https://url.retail.publishedprices.co.il/login"

    def fetch_store_list(self) -> List[str]:
        return self._fetch_via_playwright(file_types=["Stores"])

    def fetch_prices(self, store_ids: List[str]) -> List[str]:
        return self._fetch_via_playwright(store_ids=store_ids, file_types=["PriceFull", "PromoFull"])

    def _fetch_via_playwright(self, store_ids: List[str] = [], file_types: List[str] = []) -> List[str]:
        downloaded = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=True, 
                ignore_https_errors=True,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print(f"  Logging in to {self.chain_name} via Browser...")
            page.goto(self.url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            # Click Sign In / כניסה
            try:
                # Wait for form to appear
                page.wait_for_selector("form#login-form", timeout=10000)
                
                # Fill username
                page.fill("input#username", self.username)
                
                login_button = page.query_selector("button#login-button") or \
                               page.query_selector("input[type='submit']") or \
                               page.query_selector("button:has-text('Sign in')") or \
                               page.query_selector("button:has-text('כניסה')")
                if login_button:
                    print(f"    Logging in as {self.username}...")
                    login_button.click()
                    page.wait_for_load_state("networkidle")
                else:
                    print("    No login button found, attempting to proceed...")
            except Exception as e:
                print(f"    Login form/button not found or error: {e}")

            time.sleep(5) # Wait for page to load links

            # Cerberus often puts links in the main table
            links = page.query_selector_all("a")
            print(f"    Found {len(links)} total links after login.")
            
            target_links_info = []
            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()
                
                if "/file/" in href:
                    # Filter by store ID if provided
                    if store_ids:
                        if not any(f"-{sid}-" in text or f"-{sid.zfill(3)}-" in text for sid in store_ids):
                            continue
                            
                    # Filter by file types
                    if file_types and not any(t in text for t in file_types):
                        continue
                    
                    target_links_info.append({"text": text, "href": href})

            print(f"    Found {len(target_links_info)} matching files to download.")
            
            # Transfer cookies to requests session for downloading
            cookies = context.cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

            count = 0
            for info in target_links_info:
                text = info["text"]
                href = info["href"]
                
                filename = f"{self.chain_name}_{text}.gz" if not text.endswith(".gz") and not text.endswith(".xml") else f"{self.chain_name}_{text}"
                if not self._is_download_needed(filename):
                    downloaded.append(os.path.join(self.download_dir, filename))
                    continue

                try:
                    url = f"https://url.retail.publishedprices.co.il{href}"
                    dest = os.path.join(self.download_dir, filename)
                    
                    print(f"      Downloading via requests: {filename}...")
                    r = self.session.get(url, verify=False, stream=True, timeout=60)
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    downloaded.append(dest)
                    print(f"      Downloaded: {filename}")
                    count += 1
                    if count >= 15: break # Limit
                except Exception as e:
                    print(f"      Download failed for {text}: {e}")
            
            browser.close()
        return downloaded
