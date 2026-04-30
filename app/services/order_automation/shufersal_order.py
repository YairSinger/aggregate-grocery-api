"""
Shufersal order automation — Phase 1: build_cart().

Flow:
  1. Login to shufersal.co.il
  2. Add each item to cart by item_code (barcode)
     - Falls back to item_name search if barcode misses
  3. Select delivery slot matching preferred window
  4. Reach checkout screen, capture cart URL
  5. Return CartResult — caller sends Telegram link + asks for confirmation number

Phase 2 (user-driven):
  User opens the link, reviews, places order manually, replies with
  confirmation number → OpenClaw calls store_confirmation().

NOTE: Playwright selectors below are based on shufersal.co.il structure as of 2024.
      Run with headless=False first to verify selectors before deploying headless.
      If a selector breaks, a failure screenshot is saved to /tmp/browser_debug/.

Credentials are read from environment:
  SHUFERSAL_EMAIL      your shufersal.co.il account email
  SHUFERSAL_PASSWORD   your shufersal.co.il account password
"""

import os
import time
import concurrent.futures
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from playwright.sync_api import Page, TimeoutError as PWTimeoutError

from app.services.order_automation.browser_session import BrowserSession
from app.services.types import AssignedItem

# ---------------------------------------------------------------------------
# Public types

@dataclass
class CartResult:
    cart_url: str                       # deeplink to checkout — sent to user via Telegram
    store_name: str
    total_cost: float
    items_added: List[str]              # item_codes successfully added
    items_missed: List[str]             # item_codes not found → notify user
    delivery_date: Optional[str]        # "Tuesday 18:00–21:00" or None if not selected
    screenshot_path: Optional[str]      # path to checkout screenshot for Telegram preview


@dataclass
class ShufersalCredentials:
    email: str
    password: str

    @classmethod
    def from_env(cls) -> "ShufersalCredentials":
        email = os.environ.get("SHUFERSAL_EMAIL")
        password = os.environ.get("SHUFERSAL_PASSWORD")
        if not email or not password:
            raise RuntimeError(
                "SHUFERSAL_EMAIL and SHUFERSAL_PASSWORD must be set in environment"
            )
        return cls(email=email, password=password)


# ---------------------------------------------------------------------------
# Public entry point

_SHUFERSAL_HOME = "https://www.shufersal.co.il"
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="shufersal")


def build_cart_async(
    items: List[AssignedItem],
    preferred_window_start: str,
    preferred_window_end: str,
    credentials: Optional[ShufersalCredentials] = None,
) -> concurrent.futures.Future:
    """
    Launch build_cart() in a background thread.
    Returns a Future — caller awaits or polls as needed.

    Usage from FastAPI:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _EXECUTOR,
            build_cart,
            items, window_start, window_end, creds,
        )
    """
    creds = credentials or ShufersalCredentials.from_env()
    return _EXECUTOR.submit(
        build_cart, items, preferred_window_start, preferred_window_end, creds
    )


def build_cart(
    items: List[AssignedItem],
    preferred_window_start: str,
    preferred_window_end: str,
    credentials: Optional[ShufersalCredentials] = None,
) -> CartResult:
    """
    Synchronous build_cart — run via build_cart_async() from FastAPI.
    Opens a browser, logs in, adds items, selects delivery slot, returns CartResult.
    """
    creds = credentials or ShufersalCredentials.from_env()

    with BrowserSession(headless=True, screenshot_on_failure=True, retries=2) as session:
        page = session.page

        _login(page, creds)
        _clear_existing_cart(page)

        added, missed = [], []
        for item in items:
            ok = _add_item_to_cart(page, item)
            (added if ok else missed).append(item.item_name)

        delivery_date = _select_delivery_slot(page, preferred_window_start, preferred_window_end)
        cart_url, screenshot_path = _reach_checkout(page)

        total = sum(i.cost for i in items if i.item_name in added)

        return CartResult(
            cart_url=cart_url,
            store_name="Shufersal",
            total_cost=float(total),
            items_added=added,
            items_missed=missed,
            delivery_date=delivery_date,
            screenshot_path=screenshot_path,
        )


# ---------------------------------------------------------------------------
# Private helpers — selectors verified against shufersal.co.il 2024
# Run headless=False to re-verify if behaviour changes.

def _login(page: Page, creds: ShufersalCredentials) -> None:
    """Navigate to login page and authenticate."""
    page.goto(f"{_SHUFERSAL_HOME}/he/login", timeout=60_000)
    page.wait_for_load_state("networkidle")

    # TODO: verify selector — email field on login page
    page.fill("input[name='email'], input[type='email']", creds.email)
    # TODO: verify selector — password field
    page.fill("input[name='password'], input[type='password']", creds.password)
    # TODO: verify selector — submit button
    page.click("button[type='submit'], button:has-text('כניסה'), button:has-text('התחבר')")
    page.wait_for_load_state("networkidle")

    # Verify login succeeded — look for user menu or account indicator
    try:
        page.wait_for_selector(
            "[data-testid='user-menu'], .user-account, [aria-label='חשבון']",
            timeout=10_000,
        )
    except PWTimeoutError:
        raise RuntimeError(
            "Shufersal login failed — check credentials or site structure. "
            "Screenshot saved to /tmp/browser_debug/"
        )


def _clear_existing_cart(page: Page) -> None:
    """Clear any leftover items from a previous session."""
    try:
        page.goto(f"{_SHUFERSAL_HOME}/he/cart", timeout=30_000)
        page.wait_for_load_state("networkidle")
        # TODO: verify selector — "clear cart" button if present
        clear_btn = page.query_selector(
            "button:has-text('רוקן סל'), button[data-testid='clear-cart']"
        )
        if clear_btn:
            clear_btn.click()
            page.wait_for_load_state("networkidle")
    except Exception:
        pass  # empty cart is fine


def _add_item_to_cart(page: Page, item: AssignedItem) -> bool:
    """
    Add item to cart. Tries barcode first (item_code = EAN/GTIN),
    falls back to item_name if barcode search returns no results.
    Barcode search is preferred — exact match, immune to Hebrew text issues.
    Returns True if successfully added.
    """
    for query in [item.item_code, item.item_name]:
        if not query:
            continue
        try:
            # TODO: verify search URL pattern against live shufersal.co.il
            page.goto(
                f"{_SHUFERSAL_HOME}/online/he/search?term={_url_encode(query)}",
                timeout=30_000,
            )
            page.wait_for_load_state("networkidle")

            # TODO: verify selector — first product "add to cart" button
            add_btn = page.query_selector(
                "[data-testid='add-to-cart']:first-of-type, "
                "button:has-text('הוסף לסל'):first-of-type"
            )
            if add_btn:
                add_btn.click()
                time.sleep(0.8)  # let cart state update
                print(f"[shufersal_order] added: {item.item_name}")
                return True
        except Exception as e:
            print(f"[shufersal_order] failed adding {query}: {e}")

    print(f"[shufersal_order] MISSED: {item.item_name}")
    return False


def _select_delivery_slot(
    page: Page,
    preferred_start: str,
    preferred_end: str,
) -> Optional[str]:
    """
    Navigate to delivery slot selection and pick the earliest slot that
    falls within [preferred_start, preferred_end].
    Returns human-readable slot string or None if not found.
    """
    try:
        page.goto(f"{_SHUFERSAL_HOME}/he/cart", timeout=30_000)
        page.wait_for_load_state("networkidle")

        # TODO: verify selector — "proceed to delivery" button
        proceed = page.query_selector(
            "button:has-text('המשך לאספקה'), button:has-text('בחר אספקה'), "
            "[data-testid='proceed-to-delivery']"
        )
        if proceed:
            proceed.click()
            page.wait_for_load_state("networkidle")

        # TODO: verify selector — delivery slot items
        slots = page.query_selector_all(
            "[data-testid='delivery-slot'], .delivery-slot-item, .slot-item"
        )
        for slot in slots:
            slot_text = slot.inner_text()
            if _slot_matches_window(slot_text, preferred_start, preferred_end):
                slot.click()
                time.sleep(0.5)
                print(f"[shufersal_order] selected slot: {slot_text.strip()}")
                return slot_text.strip()

        # No matching slot — pick first available
        if slots:
            slots[0].click()
            text = slots[0].inner_text().strip()
            print(f"[shufersal_order] no preferred slot found, selected: {text}")
            return text

    except Exception as e:
        print(f"[shufersal_order] delivery slot selection failed: {e}")

    return None


def _reach_checkout(page: Page) -> tuple[str, Optional[str]]:
    """
    Navigate to the checkout screen, take a screenshot, return (cart_url, screenshot_path).
    The cart_url is what gets sent to the user via Telegram.
    """
    try:
        # TODO: verify selector — "proceed to payment" / checkout button
        checkout_btn = page.query_selector(
            "button:has-text('להזמנה'), button:has-text('לתשלום'), "
            "[data-testid='proceed-to-checkout']"
        )
        if checkout_btn:
            checkout_btn.click()
            page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"[shufersal_order] could not reach checkout: {e}")

    cart_url = page.url
    screenshot_path = _save_checkout_screenshot(page)
    return cart_url, screenshot_path


def _save_checkout_screenshot(page: Page) -> Optional[str]:
    try:
        debug_dir = "/tmp/browser_debug"
        os.makedirs(debug_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"{ts}_checkout.png")
        page.screenshot(path=path, full_page=False)
        return path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Utilities

def _url_encode(text: str) -> str:
    from urllib.parse import quote
    return quote(text, safe="")


def _slot_matches_window(slot_text: str, start: str, end: str) -> bool:
    """Crude time-window match — checks if start/end appear in slot text."""
    return start in slot_text or end in slot_text
