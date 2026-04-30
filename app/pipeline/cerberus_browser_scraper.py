import os
import time
from typing import List

from app.pipeline.base_scraper import ScraperBase
from app.services.order_automation.browser_session import BrowserSession


class CerberusBrowserScraper(ScraperBase):
    def __init__(self, chain_name: str, username: str, download_dir: str = "downloads"):
        super().__init__(chain_name, download_dir)
        self.username = username
        self.url = "https://url.retail.publishedprices.co.il/login"

    def fetch_store_list(self) -> List[str]:
        return self._fetch_via_browser(file_types=["Stores"])

    def fetch_prices(self, store_ids: List[str]) -> List[str]:
        return self._fetch_via_browser(store_ids=store_ids, file_types=["PriceFull", "PromoFull"])

    def _fetch_via_browser(
        self, store_ids: List[str] = [], file_types: List[str] = []
    ) -> List[str]:
        downloaded = []

        with BrowserSession(headless=True, screenshot_on_failure=True) as session:
            page = session.page

            # --- login ---
            print(f"  Logging in to {self.chain_name} via browser...")
            page.goto(self.url, timeout=60_000)
            page.wait_for_load_state("networkidle")

            try:
                page.wait_for_selector("form#login-form", timeout=10_000)
                page.fill("input#username", self.username)
                login_btn = (
                    page.query_selector("button#login-button")
                    or page.query_selector("input[type='submit']")
                    or page.query_selector("button:has-text('Sign in')")
                    or page.query_selector("button:has-text('כניסה')")
                )
                if login_btn:
                    print(f"    Logging in as {self.username}...")
                    login_btn.click()
                    page.wait_for_load_state("networkidle")
                else:
                    print("    No login button found, proceeding...")
            except Exception as e:
                print(f"    Login error: {e}")

            time.sleep(5)

            # --- collect download links ---
            links = page.query_selector_all("a")
            print(f"    Found {len(links)} links after login.")

            targets = []
            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()
                if "/file/" not in href:
                    continue
                if store_ids and not any(
                    f"-{sid}-" in text or f"-{sid.zfill(3)}-" in text
                    for sid in store_ids
                ):
                    continue
                if file_types and not any(t in text for t in file_types):
                    continue
                targets.append({"text": text, "href": href})

            print(f"    {len(targets)} matching files to download.")

            # transfer cookies to requests session for HTTP downloads
            for cookie in session.page.context.cookies():
                self.session.cookies.set(
                    cookie["name"], cookie["value"], domain=cookie["domain"]
                )

        # --- download via requests (outside BrowserSession — browser no longer needed) ---
        count = 0
        for info in targets:
            text, href = info["text"], info["href"]
            ext = ".gz" if not (text.endswith(".gz") or text.endswith(".xml")) else ""
            filename = f"{self.chain_name}_{text}{ext}"

            if not self._is_download_needed(filename):
                downloaded.append(os.path.join(self.download_dir, filename))
                continue

            try:
                url = f"https://url.retail.publishedprices.co.il{href}"
                dest = os.path.join(self.download_dir, filename)
                print(f"      Downloading: {filename}...")
                r = self.session.get(url, verify=False, stream=True, timeout=60)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded.append(dest)
                print(f"      Done: {filename}")
                count += 1
                if count >= 15:
                    break
            except Exception as e:
                print(f"      Failed {text}: {e}")

        return downloaded
