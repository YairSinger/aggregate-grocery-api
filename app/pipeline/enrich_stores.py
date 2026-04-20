"""
Download Stores XML files from each chain portal and update store names/addresses in DB.
Run once after initial data load: docker exec grocery_backend python -m app.pipeline.enrich_stores
"""
import os
import gzip
import shutil
import time
import requests
from lxml import etree
from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store
from app.pipeline.utils import normalize_hebrew_text

DOWNLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
)


def decompress_if_needed(path: str) -> str:
    if not path.endswith(".gz"):
        return path
    xml_path = path[:-3] if path.endswith(".xml.gz") else path.replace(".gz", ".xml")
    if not os.path.exists(xml_path):
        with gzip.open(path, "rb") as f_in, open(xml_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    return xml_path


def fetch_shufersal_store_names(store_ids: list[str]) -> dict[str, str]:
    """Extract store names from the Shufersal portal dropdown options.
    Returns {branch_id: store_name}."""
    names = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(ignore_https_errors=True).new_page()
        page.goto("https://prices.shufersal.co.il/", timeout=60000)
        page.wait_for_load_state("networkidle")

        opts = page.eval_on_selector_all(
            "select#ddlStore option",
            "els => els.map(e => ({val: e.value, text: e.textContent.trim()}))"
        )
        browser.close()

    for opt in opts:
        if opt["val"] in store_ids:
            # Format: "119 - דיל מודיעין- סנטר"
            text = opt["text"]
            name = text.split(" - ", 1)[1].strip() if " - " in text else text
            names[opt["val"]] = name
            print(f"    Store {opt['val']}: {name}")

    return names


def update_shufersal_from_portal(db: Session, store_ids: list[str]):
    """Update Shufersal store names by scraping the portal UI."""
    chain = db.query(Chain).filter(Chain.name == "Shufersal").first()
    if not chain:
        return
    names = fetch_shufersal_store_names(store_ids)
    updated = 0
    for store_id, name in names.items():
        stripped = store_id.lstrip("0") or store_id
        candidates = {store_id, stripped, store_id.zfill(3)}
        store = db.query(Store).filter(
            Store.chain_id == chain.id,
            Store.branch_id.in_(candidates)
        ).first()
        if store:
            store.name = name
            updated += 1
    db.commit()
    print(f"  Updated {updated} Shufersal stores")


def fetch_cerberus_stores(chain_name: str, username: str) -> str | None:
    existing = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(f"{chain_name}_Stores")]
    if existing:
        print(f"  Already downloaded: {existing[0]}")
        return os.path.join(DOWNLOAD_DIR, existing[0])

    print(f"  Fetching {chain_name} Stores via Cerberus...")
    base_url = "https://url.retail.publishedprices.co.il"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        page.goto(f"{base_url}/login", timeout=30000)
        page.wait_for_load_state("networkidle")
        page.fill('input[name="username"]', username)
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state("networkidle")

        if "/login" in page.url:
            print(f"  Login failed for {chain_name}")
            browser.close()
            return None

        time.sleep(3)
        file_links = [
            (link.get_attribute("href") or "", (link.inner_text() or "").strip())
            for link in page.query_selector_all("a")
            if "/file/d/" in (link.get_attribute("href") or "") and "Stores" in (link.inner_text() or "")
        ]
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        for cookie in context.cookies():
            session.cookies.set(cookie["name"], cookie["value"], domain=cookie["domain"])
        browser.close()

    if not file_links:
        print(f"  No Stores file found for {chain_name}")
        return None

    href, filename = file_links[0]
    dest = os.path.join(DOWNLOAD_DIR, f"{chain_name}_{filename}")
    try:
        r = session.get(f"{base_url}{href}", verify=False, stream=True, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"    Saved: {filename}")
        return dest
    except Exception as e:
        print(f"    Failed: {e}")
        return None


def _find_text(elem, *tags: str) -> str:
    for tag in tags:
        val = elem.findtext(tag)
        if val is not None:
            return val.strip()
    return ""


def parse_stores_xml(xml_path: str) -> list[dict]:
    """Parse Stores XML, handling UTF-16 encoding and StoreId/StoreID tag variants."""
    def _parse_tree(tree):
        records = []
        root = tree.getroot() if hasattr(tree, "getroot") else tree
        for store_elem in root.iter("Store"):
            branch_id = _find_text(store_elem, "StoreID", "StoreId")
            name = normalize_hebrew_text(_find_text(store_elem, "StoreName"))
            address = normalize_hebrew_text(_find_text(store_elem, "Address"))
            city = normalize_hebrew_text(_find_text(store_elem, "City"))
            if city.isdigit():
                city = ""
            records.append({"branch_id": branch_id, "name": name, "address": address, "city": city})
        return records

    try:
        return _parse_tree(etree.parse(xml_path))
    except etree.XMLSyntaxError:
        with open(xml_path, "rb") as f:
            raw = f.read()
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            raw = raw.decode("utf-16").encode("utf-8")
        return _parse_tree(etree.fromstring(raw))


def update_stores_from_file(db: Session, chain_name: str, stores_xml: str):
    chain = db.query(Chain).filter(Chain.name == chain_name).first()
    if not chain:
        print(f"  Chain {chain_name} not in DB, skipping")
        return

    records = parse_stores_xml(stores_xml)
    print(f"  Parsed {len(records)} stores from XML")

    updated = 0
    for rec in records:
        raw_id = rec.get("branch_id") or ""
        if not raw_id:
            continue
        stripped = raw_id.lstrip("0") or raw_id
        candidates = {raw_id, stripped, raw_id.zfill(3), raw_id.zfill(2)}
        store = db.query(Store).filter(
            Store.chain_id == chain.id,
            Store.branch_id.in_(candidates)
        ).first()
        if not store:
            continue
        name = rec.get("name") or ""
        city = rec.get("city") or ""
        address = rec.get("address") or ""
        store.name = f"{name}, {city}" if city and city not in name else name
        store.address = address
        updated += 1

    db.commit()
    print(f"  Updated {updated} stores for {chain_name}")


def run():
    db = SessionLocal()

    print("\n=== Shufersal ===")
    update_shufersal_from_portal(db, ["119", "134", "489"])

    for chain_name, username in [("RamiLevy", "RamiLevi"), ("Yohananof", "Yohananof")]:
        print(f"\n=== {chain_name} ===")
        stores_file = fetch_cerberus_stores(chain_name, username)
        if stores_file:
            update_stores_from_file(db, chain_name, decompress_if_needed(stores_file))
        else:
            print("  No stores file obtained")

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    run()
