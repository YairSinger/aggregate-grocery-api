import os
import re
import time
from typing import List

from app.pipeline.base_scraper import ScraperBase
from app.services.order_automation.browser_session import BrowserSession


class ShufersalScraper(ScraperBase):
    def __init__(self, download_dir: str = "downloads"):
        super().__init__("Shufersal", download_dir)
        self.url = "https://prices.shufersal.co.il/"

    def fetch_store_list(self) -> List[str]:
        return self._fetch_via_browser(store_ids=["134"], category="0", file_types=["Stores"])

    def fetch_prices(self, store_ids: List[str]) -> List[str]:
        downloaded = []
        downloaded.extend(self._fetch_via_browser(store_ids=store_ids, category="2", file_types=["PriceFull"]))
        downloaded.extend(self._fetch_via_browser(store_ids=store_ids, category="4", file_types=["PromoFull"]))
        return downloaded

    def _fetch_via_browser(
        self,
        store_ids: List[str],
        category: str = "0",
        file_types: List[str] = [],
    ) -> List[str]:
        downloaded = []
        with BrowserSession(headless=True, screenshot_on_failure=True) as session:
            page = session.page
            page.goto(self.url, timeout=60_000)
            page.wait_for_load_state("networkidle")

            for store_id in store_ids:
                print(f"  Selecting Shufersal Store {store_id} in category {category}...")
                try:
                    page.select_option("select#ddlStore", value=store_id)
                    time.sleep(3)
                    page.select_option("select#ddlCategory", value=category)
                    time.sleep(7)

                    links = page.query_selector_all("a")
                    download_links = [
                        l for l in links
                        if "blob.core.windows.net" in (l.get_attribute("href") or "")
                    ]
                    print(f"    Found {len(download_links)} data links.")

                    for link in download_links:
                        href = link.get_attribute("href") or ""
                        if file_types and not any(t in href for t in file_types):
                            continue

                        match = re.search(r"(PriceFull|Price|PromoFull|Promo|Stores)[^?]*", href)
                        basename = match.group(0) if match else f"data_{int(time.time())}"
                        filename = (
                            f"Shufersal_{store_id}_{basename}.gz"
                            if not basename.endswith(".gz")
                            else f"Shufersal_{store_id}_{basename}"
                        )

                        if not self._is_download_needed(filename):
                            downloaded.append(os.path.join(self.download_dir, filename))
                            continue

                        try:
                            with page.expect_download(timeout=60_000) as dl_info:
                                link.click()
                            dest = os.path.join(self.download_dir, filename)
                            dl_info.value.save_as(dest)
                            downloaded.append(dest)
                            print(f"      Downloaded: {filename}")
                        except Exception as e:
                            print(f"      Download failed: {e}")

                except Exception as e:
                    print(f"    Failed for store {store_id}: {e}")

        return downloaded
