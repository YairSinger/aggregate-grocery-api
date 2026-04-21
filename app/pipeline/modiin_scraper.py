import os
import re
import gzip
import shutil
from typing import Dict, List, Tuple
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price
from app.pipeline.parser import GroceryParser
from app.pipeline.processor import DataProcessor

CHAIN_CONFIGS = {
    "Shufersal": {"official_id": "7290027600007"},
    "RamiLevy":  {"official_id": "7290058140886"},
    "Yohananof": {"official_id": "7290803800003"},
}

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")


def decompress_gz(file_path: str) -> str:
    xml_path = file_path.rsplit(".gz", 1)[0]
    if not xml_path.endswith(".xml"):
        xml_path += ".xml"
    if os.path.exists(xml_path):
        return xml_path
    with gzip.open(file_path, "rb") as f_in, open(xml_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    return xml_path


def extract_store_id(filename: str) -> str:
    """Extract store branch ID from filename like PriceFull7290027600007-119-20260419.gz"""
    m = re.search(r"(?:PriceFull|PromoFull)\d+-(\d+)-", filename)
    return m.group(1) if m else "000"


def group_files_by_store(download_dir: str) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
    """Returns {chain_name: {store_id: {PriceFull: [files], PromoFull: [files]}}}"""
    groups: Dict[str, Dict[str, Dict[str, List[str]]]] = {}
    for fname in os.listdir(download_dir):
        if not fname.endswith(".gz"):
            continue
        # Filename: {ChainName}_PriceFull... or {ChainName}_PromoFull...
        parts = fname.split("_", 1)
        if len(parts) != 2:
            continue
        chain_name, rest = parts
        if chain_name not in CHAIN_CONFIGS:
            continue
        file_type = "PriceFull" if "PriceFull" in rest else ("PromoFull" if "PromoFull" in rest else None)
        if not file_type:
            continue
        store_id = extract_store_id(rest)
        groups.setdefault(chain_name, {}).setdefault(store_id, {"PriceFull": [], "PromoFull": []})
        groups[chain_name][store_id][file_type].append(os.path.join(download_dir, fname))
    return groups


def save_processed_data(db: Session, processed_data: List[Dict], store_id: str, chain_id: str):
    count = 0
    for data in processed_data:
        item = db.query(Item).filter(
            Item.chain_id == chain_id,
            Item.item_code == data["item"]["item_code"],
        ).first()
        if not item:
            item = Item(**data["item"])
            db.add(item)
            db.flush()

        price = db.query(Price).filter(
            Price.item_id == item.id, Price.store_id == store_id
        ).first()
        if price:
            for k, v in data["price"].items():
                setattr(price, k, v)
        else:
            db.add(Price(item_id=item.id, store_id=store_id, **data["price"]))

        count += 1
        if count % 1000 == 0:
            db.commit()
    db.commit()
    return count


def scrape_modiin():
    db = SessionLocal()
    parser = GroceryParser()
    processor = DataProcessor()
    download_dir = os.path.abspath(DOWNLOAD_DIR)

    file_groups = group_files_by_store(download_dir)
    print(f"Found downloads for chains: {list(file_groups.keys())}")

    for chain_name, stores in file_groups.items():
        config = CHAIN_CONFIGS[chain_name]
        print(f"\n=== Processing {chain_name} ({len(stores)} stores) ===")

        chain = db.query(Chain).filter(Chain.official_id == config["official_id"]).first()
        if not chain:
            chain = Chain(name=chain_name, official_id=config["official_id"])
            db.add(chain)
            db.commit()
            db.refresh(chain)

        for store_id, files in stores.items():
            price_files = sorted(files["PriceFull"])
            promo_files = sorted(files["PromoFull"])
            if not price_files:
                print(f"  Store {store_id}: no PriceFull file, skipping")
                continue

            # Use the most recent file (sorted alphabetically = chronologically by date suffix)
            price_gz = price_files[-1]
            promo_gz = promo_files[-1] if promo_files else None

            store_db = db.query(Store).filter(
                Store.chain_id == chain.id, Store.branch_id == store_id
            ).first()
            if not store_db:
                store_db = Store(
                    chain_id=chain.id,
                    branch_id=store_id,
                    name=f"{chain_name} Store {store_id}",
                    address="",
                )
                db.add(store_db)
                db.commit()
                db.refresh(store_db)

            print(f"  Store {store_id}: parsing {os.path.basename(price_gz)}...")
            try:
                price_xml = decompress_gz(price_gz)
                promo_xml = decompress_gz(promo_gz) if promo_gz else None

                price_items = parser.parse_price_file(price_xml)
                promo_data = parser.parse_promo_file(promo_xml) if promo_xml else []

                processed = processor.process_store_prices(
                    price_items, promo_data, str(store_db.id), str(chain.id)
                )
                n = save_processed_data(db, processed, store_db.id, chain.id)
                print(f"    Saved {n} items")
            except Exception as e:
                print(f"    Error: {e}")
                db.rollback()

    db.close()
    print("\nDone.")


if __name__ == "__main__":
    scrape_modiin()
