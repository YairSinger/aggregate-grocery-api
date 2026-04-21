import os
import gzip
import shutil
from typing import List, Dict
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price
from app.pipeline.factory import ScraperFactory
from app.pipeline.parser import GroceryParser
from app.pipeline.processor import DataProcessor

# Target Modiin Store IDs from DATA_ACQUISITION.md
TARGET_CONFIG = {
    "Shufersal": {
        "official_id": "7290027600007",
        "store_ids": ["119", "134", "489"]
    },
    "RamiLevy": {
        "official_id": "7290058140886",
        "store_ids": ["101", "102"]
    },
    "Victory": {
        "official_id": "7290696200003",
        "store_ids": ["201"]
    },
    "Yohananof": {
        "official_id": "7290803800003",
        "store_ids": ["15"] # Example for Modiin/Shilat
    }
}

def decompress_gz(file_path: str) -> str:
    xml_path = file_path.replace('.gz', '.xml')
    if not xml_path.endswith('.xml'):
        xml_path += '.xml'
    
    if os.path.exists(xml_path):
        # Check if gz is newer than xml
        if os.path.getmtime(file_path) > os.path.getmtime(xml_path):
            pass # Re-decompress
        else:
            return xml_path

    print(f"Decompressing {os.path.basename(file_path)}...")
    with gzip.open(file_path, 'rb') as f_in:
        with open(xml_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return xml_path

def save_data(db: Session, processed_data: List[Dict], store_id: int, chain_id: int):
    """Efficiently save processed data to the database."""
    print(f"  Saving {len(processed_data)} items to DB...")
    count = 0
    for data in processed_data:
        # 1. Handle Item
        item = db.query(Item).filter(
            Item.chain_id == chain_id, 
            Item.item_code == data["item"]["item_code"]
        ).first()
        
        if not item:
            item = Item(**data["item"])
            db.add(item)
            db.flush()
        else:
            # Always refresh mutable item fields so pipeline re-runs fix stale data
            for field in ("name", "brand", "category", "unit_of_measure", "quantity"):
                if field in data["item"]:
                    setattr(item, field, data["item"][field])

        # 2. Handle Price
        price = db.query(Price).filter(
            Price.item_id == item.id, 
            Price.store_id == store_id
        ).first()
        
        if price:
            for k, v in data["price"].items():
                setattr(price, k, v)
        else:
            price = Price(
                item_id=item.id,
                store_id=store_id,
                **data["price"]
            )
            db.add(price)
        
        count += 1
        if count % 1000 == 0:
            db.commit()
            print(f"    Saved {count} items...")
    db.commit()

def run_improved_pipeline():
    db = SessionLocal()
    parser = GroceryParser()
    processor = DataProcessor()
    
    for chain_name, config in TARGET_CONFIG.items():
        print(f"\n=== Processing {chain_name} ===")
        try:
            # 1. Ensure Chain exists
            chain = db.query(Chain).filter(Chain.official_id == config["official_id"]).first()
            if not chain:
                chain = Chain(name=chain_name, official_id=config["official_id"])
                db.add(chain)
                db.commit()
                db.refresh(chain)

            # 2. Scrape files
            scraper = ScraperFactory.get_scraper(chain_name)
            
            # Fetch Store List if needed (optional but good for metadata)
            # stores_files = scraper.fetch_store_list()
            
            # Fetch Prices
            price_files = scraper.fetch_prices(config["store_ids"])
            print(f"  Found {len(price_files)} files to process.")

            # 3. Group files by store ID
            store_groups = {}
            for f in price_files:
                # Find which store ID this file belongs to
                sid = next((sid for sid in config["store_ids"] if f"-{sid}-" in f or f"-{sid.zfill(3)}-" in f or f"_{sid}_" in f), config["store_ids"][0])
                if sid not in store_groups: store_groups[sid] = {}
                
                if "PriceFull" in f: store_groups[sid]["price"] = f
                if "PromoFull" in f: store_groups[sid]["promo"] = f

            # 4. Process each store
            for sid, files in store_groups.items():
                if "price" not in files:
                    print(f"  Missing PriceFull for store {sid}, skipping.")
                    continue
                
                print(f"  Processing Store {sid}...")
                
                # Ensure Store exists in DB
                store_db = db.query(Store).filter(Store.chain_id == chain.id, Store.branch_id == sid).first()
                if not store_db:
                    # In a real scenario, we'd get name/address from the Stores XML
                    store_db = Store(
                        chain_id=chain.id,
                        branch_id=sid,
                        name=f"{chain_name} - {sid}",
                        address="Address from XML"
                    )
                    db.add(store_db)
                    db.commit()
                    db.refresh(store_db)

                p_xml = decompress_gz(files["price"])
                pr_xml = decompress_gz(files["promo"]) if "promo" in files else None
                
                price_items = parser.parse_price_file(p_xml)
                promo_data = parser.parse_promo_file(pr_xml) if pr_xml else []
                
                processed = processor.process_store_prices(
                    price_items, promo_data, str(store_db.id), str(chain.id)
                )
                
                save_data(db, processed, store_db.id, chain.id)

        except Exception as e:
            print(f"Error processing {chain_name}: {e}")
            db.rollback()

    db.close()

if __name__ == "__main__":
    run_improved_pipeline()
