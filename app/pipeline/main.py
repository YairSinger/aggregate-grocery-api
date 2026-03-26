import os
import gzip
import shutil
from typing import List
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price
from app.pipeline.downloader import ChainDownloader
from app.pipeline.parser import GroceryParser
from app.pipeline.processor import DataProcessor

def decompress_gz(file_path: str) -> str:
    xml_path = file_path.replace('.gz', '.xml')
    if not xml_path.endswith('.xml'):
        xml_path += '.xml'
        
    with gzip.open(file_path, 'rb') as f_in:
        with open(xml_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    return xml_path

def run_pipeline():
    db = SessionLocal()
    downloader = ChainDownloader()
    parser = GroceryParser()
    processor = DataProcessor()

    try:
        # 1. Initialize Chain (e.g., Shufersal)
        chain = db.query(Chain).filter(Chain.official_id == "7290027600007").first()
        if not chain:
            chain = Chain(name="Shufersal", official_id="7290027600007")
            db.add(chain)
            db.commit()
            db.refresh(chain)

        # 2. Download latest files
        gz_files = downloader.download_shufersal()
        
        # 3. Process each file
        price_file = None
        promo_file = None
        
        for f in gz_files:
            xml_file = decompress_gz(f)
            if "PriceFull" in xml_file:
                price_file = xml_file
            elif "PromoFull" in xml_file:
                promo_file = xml_file

        if price_file and promo_file:
            print("Parsing PriceFull and PromoFull...")
            price_items = parser.parse_price_file(price_file)
            promo_data = parser.parse_promo_file(promo_file)
            
            # For MVP: assume single store from the file metadata
            # In a full run, we would parse StoreId from the XML header
            store_id_xml = "001" # Default placeholder
            
            store = db.query(Store).filter(
                Store.chain_id == chain.id, 
                Store.branch_id == store_id_xml
            ).first()
            
            if not store:
                store = Store(
                    chain_id=chain.id,
                    branch_id=store_id_xml,
                    name=f"Shufersal - {store_id_xml}",
                    address="Unknown Address"
                )
                db.add(store)
                db.commit()
                db.refresh(store)

            print(f"Processing {len(price_items)} items...")
            processed_data = processor.process_store_prices(
                price_items, promo_data, str(store.id), str(chain.id)
            )

            print("Loading into database...")
            for data in processed_data:
                # 1. Update or create item
                item = db.query(Item).filter(
                    Item.chain_id == chain.id, 
                    Item.item_code == data["item"]["item_code"]
                ).first()
                
                if not item:
                    item = Item(**data["item"])
                    db.add(item)
                    db.flush() # Get item.id

                # 2. Update or create price
                price = db.query(Price).filter(
                    Price.item_id == item.id, 
                    Price.store_id == store.id
                ).first()
                
                if price:
                    # Update existing price
                    for k, v in data["price"].items():
                        setattr(price, k, v)
                else:
                    price = Price(
                        item_id=item.id,
                        store_id=store.id,
                        **data["price"]
                    )
                    db.add(price)

            db.commit()
            print("Pipeline run successful.")

    except Exception as e:
        print(f"Pipeline error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_pipeline()
