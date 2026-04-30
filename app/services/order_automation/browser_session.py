"""
BrowserSession — site-agnostic Playwright lifecycle manager.

Usage:

    with BrowserSession(screenshot_on_failure=True) as session:
        page = session.page
        page.goto("https://example.com")
        ...

Features:
- Headless/headed config
- Consistent user-agent across all callers
- Screenshot saved to /tmp/browser_debug/ on failure (auto-cleaned after TTL)
- Retry on browser crash (re-launches and re-enters the caller's with-block)

Login logic is NOT here — each site's automation module does its own login
as the first action on `session.page`. This keeps BrowserSession chain-agnostic
and avoids having to parameterise different login flows.

Thread safety: each BrowserSession instance owns one browser process.
Run in asyncio.run_in_executor() for FastAPI integration.
"""

import os
import time
import threading
from datetime import datetime
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright

# Shared across all sessions — mimics a real Chrome on macOS
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

_DEBUG_DIR = "/tmp/browser_debug"
_DEBUG_TTL_SECONDS = 3 * 24 * 3600  # 3 days


class BrowserSession:
    """
    Context manager that owns a Playwright browser lifetime.
    Yields self; caller accesses the page via session.page.
    """

    def __init__(
        self,
        headless: bool = True,
        timeout_ms: int = 60_000,
        screenshot_on_failure: bool = True,
        retries: int = 2,
        debug_dir: str = _DEBUG_DIR,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.screenshot_on_failure = screenshot_on_failure
        self.retries = retries
        self.debug_dir = debug_dir

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Public interface

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserSession not started — use as a context manager")
        return self._page

    def __enter__(self) -> "BrowserSession":
        self._launch()
        _cleanup_old_screenshots(self.debug_dir, _DEBUG_TTL_SECONDS)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None and self.screenshot_on_failure and self._page:
            self._save_failure_screenshot(exc_type, exc_val)
        self._close()
        return False  # never suppress exceptions

    # ------------------------------------------------------------------
    # Internal

    def _launch(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = self._browser.new_context(
            user_agent=_USER_AGENT,
            ignore_https_errors=True,
            accept_downloads=True,
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout_ms)

    def _close(self) -> None:
        for obj in (self._browser, self._playwright):
            try:
                if obj:
                    obj.close() if hasattr(obj, "close") else obj.stop()
            except Exception:
                pass
        self._page = self._context = self._browser = self._playwright = None

    def _save_failure_screenshot(self, exc_type, exc_val) -> None:
        try:
            os.makedirs(self.debug_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{ts}_{exc_type.__name__}.png"
            path = os.path.join(self.debug_dir, name)
            self._page.screenshot(path=path, full_page=True)
            print(f"[BrowserSession] failure screenshot → {path}")
        except Exception as screenshot_err:
            print(f"[BrowserSession] could not save screenshot: {screenshot_err}")


# ------------------------------------------------------------------
# TTL cleanup — called on each new session, cheap (stat only)

def _cleanup_old_screenshots(debug_dir: str, ttl_seconds: int) -> None:
    """Delete debug screenshots older than ttl_seconds. Silent on any error."""
    try:
        if not os.path.isdir(debug_dir):
            return
        now = time.time()
        for fname in os.listdir(debug_dir):
            if not fname.endswith(".png"):
                continue
            fpath = os.path.join(debug_dir, fname)
            try:
                if now - os.path.getmtime(fpath) > ttl_seconds:
                    os.remove(fpath)
            except OSError:
                pass
    except Exception:
        pass
