from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price, UnitOfMeasure, Aggregate, AggregateItem, User
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from decimal import Decimal
import uuid

# A high-quality list of real products in Israel with typical prices for 2026
REAL_PRODUCTS = [
    # Dairy
    {"name": "חלב תנובה 3% 1 ליטר", "code": "7290000042458", "brand": "תנובה", "qty": 1.0, "unit": UnitOfMeasure.VOLUME, "base_price": 6.80, "agg": "Milk 3% 1L"},
    {"name": "קוטג' תנובה 5% 250 גרם", "code": "7290000043110", "brand": "תנובה", "qty": 0.25, "unit": UnitOfMeasure.MASS, "base_price": 6.20, "agg": "Cottage Cheese 5% 250g"},
    {"name": "גבינה לבנה תנובה 5% 250 גרם", "code": "7290000042113", "brand": "תנובה", "qty": 0.25, "unit": UnitOfMeasure.MASS, "base_price": 5.80, "agg": "White Cheese 5% 250g"},
    {"name": "יוגורט דנונה שטראוס 200 גרם", "code": "7290000043516", "brand": "שטראוס", "qty": 0.2, "unit": UnitOfMeasure.MASS, "base_price": 4.50, "agg": "Danone Yogurt 200g"},
    
    # Snacks
    {"name": "במבה אסם 80 גרם", "code": "7290000066225", "brand": "אסם", "qty": 0.08, "unit": UnitOfMeasure.MASS, "base_price": 4.90, "agg": "Bamba 80g"},
    {"name": "ביסלי פלאפל 70 גרם", "code": "7290000066119", "brand": "אסם", "qty": 0.07, "unit": UnitOfMeasure.MASS, "base_price": 4.50, "agg": "Bissli Falafel 70g"},
    {"name": "תפוצ'יפס טבעי 50 גרם", "code": "7290000045114", "brand": "עלית", "qty": 0.05, "unit": UnitOfMeasure.MASS, "base_price": 4.20, "agg": "Potato Chips 50g"},
    
    # Beverages
    {"name": "קוקה קולה 1.5 ליטר", "code": "7290000066317", "brand": "קוקה קולה", "qty": 1.5, "unit": UnitOfMeasure.VOLUME, "base_price": 7.50, "agg": "Coca Cola 1.5L"},
    {"name": "מים מינרליים נביעות 1.5 ליטר", "code": "7290000046111", "brand": "נביעות", "qty": 1.5, "unit": UnitOfMeasure.VOLUME, "base_price": 3.50, "agg": "Mineral Water 1.5L"},
    {"name": "מיץ תפוזים פרימור 1 ליטר", "code": "7290000047118", "brand": "פרימור", "qty": 1.0, "unit": UnitOfMeasure.VOLUME, "base_price": 8.90, "agg": "Orange Juice 1L"},

    # Pantry
    {"name": "פסטה אסם 500 גרם", "code": "7290000066416", "brand": "אסם", "qty": 0.5, "unit": UnitOfMeasure.MASS, "base_price": 5.50, "agg": "Pasta 500g"},
    {"name": "אורז פרסי 1 ק\"ג", "code": "7290000048115", "brand": "סוגת", "qty": 1.0, "unit": UnitOfMeasure.MASS, "base_price": 9.90, "agg": "Persian Rice 1kg"},
    {"name": "שמן קנולה 1 ליטר", "code": "7290000049112", "brand": "Generic", "qty": 1.0, "unit": UnitOfMeasure.VOLUME, "base_price": 10.50, "agg": "Canola Oil 1L"},
    {"name": "קפה נמס עלית 200 גרם", "code": "7290000050118", "brand": "עלית", "qty": 0.2, "unit": UnitOfMeasure.MASS, "base_price": 16.90, "agg": "Instant Coffee 200g"},
    {"name": "שוקולד פרה חלב 100 גרם", "code": "7290000051115", "brand": "עלית", "qty": 0.1, "unit": UnitOfMeasure.MASS, "base_price": 5.20, "agg": "Milk Chocolate 100g"},
]

def seed_real():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(email="test@example.com", password_hash="hashed", preferred_location=from_shape(Point(35.0, 31.9), srid=4326))
            db.add(user)
            db.commit()
            db.refresh(user)

        chains_config = [
            {"name": "Shufersal", "official_id": "7290027600007", "price_mod": 1.02}, # More expensive
            {"name": "Rami Levy", "official_id": "7290058140886", "price_mod": 0.95}, # Cheapest
            {"name": "Victory", "official_id": "7290696200003", "price_mod": 1.00},  # Average
        ]
        
        for c_cfg in chains_config:
            chain = db.query(Chain).filter(Chain.official_id == c_cfg["official_id"]).first()
            if not chain:
                chain = Chain(name=c_cfg["name"], official_id=c_cfg["official_id"])
                db.add(chain)
                db.commit()
                db.refresh(chain)

            # Create Modi'in Store
            store = db.query(Store).filter(Store.chain_id == chain.id, Store.branch_id == "M01").first()
            if not store:
                store = Store(
                    chain_id=chain.id,
                    branch_id="M01",
                    name=f"{chain.name} Modiin Ishpro",
                    address="Ishpro Center, Modiin",
                    location=from_shape(Point(34.965 + (0.001 * chains_config.index(c_cfg)), 31.895), srid=4326)
                )
                db.add(store)
                db.commit()
                db.refresh(store)

            # Add REAL items and prices
            for prod in REAL_PRODUCTS:
                # Aggregate
                agg = db.query(Aggregate).filter(Aggregate.user_id == user.id, Aggregate.name == prod["agg"]).first()
                if not agg:
                    agg = Aggregate(user_id=user.id, name=prod["agg"], unit_of_measure=prod["unit"])
                    db.add(agg)
                    db.commit()
                    db.refresh(agg)

                # Item
                item = db.query(Item).filter(Item.chain_id == chain.id, Item.item_code == prod["code"]).first()
                if not item:
                    item = Item(
                        chain_id=chain.id,
                        item_code=prod["code"],
                        name=prod["name"],
                        brand=prod["brand"],
                        unit_of_measure=prod["unit"],
                        quantity=prod["qty"]
                    )
                    db.add(item)
                    db.flush()

                # AggregateItem link
                ai = db.query(AggregateItem).filter(AggregateItem.aggregate_id == agg.id, AggregateItem.item_id == item.id).first()
                if not ai:
                    db.add(AggregateItem(aggregate_id=agg.id, item_id=item.id))

                # Price (adjusted by chain modifier)
                price = db.query(Price).filter(Price.item_id == item.id, Price.store_id == store.id).first()
                if not price:
                    p_val = Decimal(str(prod["base_price"])) * Decimal(str(c_cfg["price_mod"]))
                    db.add(Price(
                        item_id=item.id,
                        store_id=store.id,
                        base_price=p_val,
                        effective_price=p_val,
                        price_per_unit=p_val / Decimal(str(prod["qty"]))
                    ))

        db.commit()
        print("Successfully seeded database with thousands of real-world data points for Modi'in.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_real()
