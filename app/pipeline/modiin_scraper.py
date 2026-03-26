import os
import gzip
import shutil
import time
from typing import List, Dict
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price
from app.pipeline.browser_downloader import BrowserDownloader
from app.pipeline.parser import GroceryParser
from app.pipeline.processor import DataProcessor

def decompress_gz(file_path: str) -> str:
    xml_path = file_path.replace('.gz', '.xml')
    if not xml_path.endswith('.xml'):
        xml_path += '.xml'
    
    if os.path.exists(xml_path):
        return xml_path

    print(f"Decompressing {file_path}...")
    with gzip.open(file_path, 'rb') as f_in:
        with open(xml_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return xml_path

def save_processed_data(db: Session, processed_data: List[Dict], store_id: str, chain_id: str):
    print(f"Saving {len(processed_data)} items for store {store_id}...")
    count = 0
    for data in processed_data:
        item = db.query(Item).filter(
            Item.chain_id == chain_id, 
            Item.item_code == data["item"]["item_code"]
        ).first()
        
        if not item:
            item = Item(**data["item"])
            db.add(item)
            db.flush() 

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
    db.commit()

def scrape_modiin():
    db = SessionLocal()
    downloader = BrowserDownloader()
    parser = GroceryParser()
    processor = DataProcessor()
    
    city = "מודיעין"
    
    chains_config = {
        "Shufersal": {"id": "7290027600007"},
        "RamiLevy": {"id": "7290058140886"},
        "Victory": {"id": "7290696200003"},
    }

    print("Starting Browser-based Bulk scraping (Real Data)...")
    all_files = downloader.scrape_all()

    for name, config in chains_config.items():
        print(f"\n=== Processing Bulk Data for {name} ===")
        try:
            chain = db.query(Chain).filter(Chain.official_id == config["id"]).first()
            if not chain:
                chain = Chain(name=name, official_id=config["id"])
                db.add(chain)
                db.commit()
                db.refresh(chain)

            files = all_files.get(name, [])
            stores_file = next((f for f in files if "Stores" in f), None)
            
            if not stores_file:
                print(f"No stores file found for {name}")
                continue

            stores_xml = decompress_gz(stores_file)
            modiin_branches = parser.parse_store_file(stores_xml, city_filter=city)
            print(f"Found {len(modiin_branches)} branches in {city} for {name}")

            for branch in modiin_branches:
                bid = branch["branch_id"]
                print(f"  -> Branch {bid}: {branch['name']}")
                
                # Check if we have a file for this branch specifically
                # For Rami Levy/Victory, filenames often contain the branch ID
                branch_price_file = next((f for f in files if "PriceFull" in f and (f"-{bid}-" in f or f"-{bid.zfill(3)}-" in f)), None)
                branch_promo_file = next((f for f in files if "PromoFull" in f and (f"-{bid}-" in f or f"-{bid.zfill(3)}-" in f)), None)
                
                # Fallback to the first found PriceFull/PromoFull for Shufersal (which uses global files for some sub-chains)
                if not branch_price_file:
                    branch_price_file = next((f for f in files if "PriceFull" in f), None)
                if not branch_promo_file:
                    branch_promo_file = next((f for f in files if "PromoFull" in f), None)

                if branch_price_file and branch_promo_file:
                    store_db = db.query(Store).filter(Store.chain_id == chain.id, Store.branch_id == bid).first()
                    if not store_db:
                        store_db = Store(
                            chain_id=chain.id,
                            branch_id=bid,
                            name=branch["name"],
                            address=branch["address"]
                        )
                        db.add(store_db)
                        db.commit()
                        db.refresh(store_db)

                    p_xml = decompress_gz(branch_price_file)
                    pr_xml = decompress_gz(branch_promo_file)
                    
                    print(f"    Parsing and Saving items for {branch['name']}...")
                    price_items = parser.parse_price_file(p_xml)
                    promo_data = parser.parse_promo_file(pr_xml)
                    
                    processed = processor.process_store_prices(
                        price_items, promo_data, str(store_db.id), str(chain.id)
                    )
                    save_processed_data(db, processed, store_db.id, chain.id)
                else:
                    print(f"    No specific Price/Promo files found for branch {bid}")

        except Exception as e:
            print(f"Error processing {name}: {e}")
            db.rollback()

    db.close()

if __name__ == "__main__":
    scrape_modiin()
