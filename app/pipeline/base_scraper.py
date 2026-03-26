import os
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class ScraperBase(ABC):
    def __init__(self, chain_name: str, download_dir: str = "downloads"):
        self.chain_name = chain_name
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        })

    @abstractmethod
    def fetch_store_list(self) -> List[str]:
        """Fetch the list of stores for this chain."""
        pass

    @abstractmethod
    def fetch_prices(self, store_ids: List[str]) -> List[str]:
        """Fetch the price files for specific stores."""
        pass

    def _is_download_needed(self, filename: str) -> bool:
        """Check if we already have a recent version of this file."""
        dest = os.path.join(self.download_dir, filename)
        if not os.path.exists(dest):
            return True
        
        # Simple check: if file is older than 12 hours, re-download
        import time
        file_age = time.time() - os.path.getmtime(dest)
        if file_age > 12 * 3600:
            return True
        
        return False

    def _download_file(self, url: str, filename: str) -> Optional[str]:
        """Helper to download a file with basic retry logic."""
        dest = os.path.join(self.download_dir, filename)
        
        if not self._is_download_needed(filename):
            print(f"  Skipping {filename} (already exists and fresh)")
            return dest

        print(f"  Downloading {filename}...")
        for attempt in range(3):
            try:
                r = self.session.get(url, verify=False, stream=True, timeout=30)
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                return dest
            except Exception as e:
                print(f"    Attempt {attempt+1} failed for {filename}: {e}")
                import time
                time.sleep(2)
        return None
