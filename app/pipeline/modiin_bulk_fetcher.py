import os
import time
import requests
from lxml import html
from playwright.sync_api import sync_playwright
from typing import List, Dict

# Verified Modiin Store IDs
MODIIN_IDS = {
    "Shufersal": ["119", "134", "489"],
    "RamiLevy": [],   # no store-ID filter; portal doesn't expose Stores file
    "Yohananof": [],  # no store-ID filter
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
        """Uses Playwright to extract Azure blob links for specific Modiin stores, then downloads via requests."""
        print("--- Fetching Shufersal (Modiin) ---")
        TARGET_TYPES = ["pricefull", "promofull"]
        downloaded = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            page.goto("https://prices.shufersal.co.il/", timeout=60000)
            page.wait_for_load_state("networkidle")

            for store_id in MODIIN_IDS["Shufersal"]:
                print(f"  Selecting Store {store_id}...")
                try:
                    page.select_option("select#ddlStore", value=store_id)
                    time.sleep(2)
                    page.select_option("select#ddlCategory", value="0")
                    time.sleep(5)

                    links = page.query_selector_all("a")
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if "blob.core.windows.net" not in href:
                            continue
                        # Only download PriceFull and PromoFull
                        href_lower = href.lower()
                        if not any(t in href_lower for t in TARGET_TYPES):
                            continue
                        # Derive a clean filename from the URL path
                        fname = href.split("?")[0].split("/")[-1]
                        dest = os.path.join(self.download_dir, f"Shufersal_{fname}")
                        if os.path.exists(dest):
                            print(f"    Already exists: {fname}")
                            downloaded.append(dest)
                            continue
                        try:
                            r = self.session.get(href, stream=True, timeout=60)
                            r.raise_for_status()
                            with open(dest, "wb") as f:
                                for chunk in r.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            downloaded.append(dest)
                            print(f"    Downloaded: {fname}")
                        except Exception as e:
                            print(f"    Failed to download {fname}: {e}")
                except Exception as e:
                    print(f"    Failed for store {store_id}: {e}")

            browser.close()
        return downloaded

    def fetch_cerberus(self, chain_name: str, username: str):
        """Uses Playwright for login + file listing, then requests for downloads."""
        print(f"--- Fetching {chain_name} (Modiin) ---")
        base_url = "https://url.retail.publishedprices.co.il"
        target_ids = MODIIN_IDS.get(chain_name, [])
        TARGET_TYPES = ["PriceFull", "PromoFull", "Stores"]
        downloaded = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()

            page.goto(f"{base_url}/login", timeout=30000)
            page.wait_for_load_state("networkidle")
            page.fill('input[name="username"]', username)
            try:
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("networkidle")
            except Exception as e:
                print(f"  Login click failed: {e}")
                browser.close()
                return []

            if "/login" in page.url:
                print(f"  Login failed for {chain_name} (still on login page)")
                browser.close()
                return []

            time.sleep(3)

            # Collect all file links
            links = page.query_selector_all("a")
            file_links = []
            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()
                if "/file/d/" in href and text:
                    file_links.append((href, text))

            print(f"  Found {len(file_links)} total files")

            # Transfer browser cookies to requests session
            session = requests.Session()
            session.headers.update({"User-Agent": "Mozilla/5.0"})
            for cookie in context.cookies():
                session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"])

            browser.close()

        # Filter and download
        for href, filename in file_links:
            id_match = (not target_ids) or any(
                f"-{bid}-" in filename or f"-{bid.zfill(3)}-" in filename
                for bid in target_ids
            )
            if not (id_match and any(t in filename for t in TARGET_TYPES)):
                continue

            dest = os.path.join(self.download_dir, f"{chain_name}_{filename}")
            if os.path.exists(dest):
                print(f"  Already exists: {filename}")
                downloaded.append(dest)
                continue

            print(f"  Downloading {filename}...")
            try:
                r = session.get(f"{base_url}{href}", verify=False, stream=True, timeout=60)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                downloaded.append(dest)
            except Exception as e:
                print(f"    Failed: {e}")

            if len(downloaded) >= 20:
                break

        return downloaded

    def run_all(self):
        results = {}
        results["Shufersal"] = self.fetch_shufersal()
        results["RamiLevy"] = self.fetch_cerberus("RamiLevy", "RamiLevi")
        results["Yohananof"] = self.fetch_cerberus("Yohananof", "Yohananof")
        return results

if __name__ == "__main__":
    fetcher = ModiinBulkFetcher()
    fetcher.run_all()
