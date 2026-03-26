from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Chain, Store, Item, Price, UnitOfMeasure, Aggregate, AggregateItem, User
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from decimal import Decimal
import uuid

def seed():
    db = SessionLocal()
    try:
        # 0. Create a Test User
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(
                email="test@example.com",
                password_hash="hashed_password",
                preferred_location=from_shape(Point(35.0000, 31.9000), srid=4326)
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 1. Create Chains
        chains_config = [
            {"name": "Shufersal", "official_id": "7290027600007"},
            {"name": "Rami Levy", "official_id": "7290058140886"},
            {"name": "Victory", "official_id": "7290696200003"},
        ]
        chains = {}
        for cfg in chains_config:
            c = db.query(Chain).filter(Chain.official_id == cfg["official_id"]).first()
            if not c:
                c = Chain(name=cfg["name"], official_id=cfg["official_id"])
                db.add(c)
                db.commit()
                db.refresh(c)
            chains[cfg["name"]] = c

        # 2. Create Stores in Modi'in
        stores_config = [
            {"chain": "Shufersal", "branch": "001", "name": "Shufersal Deal Modiin", "addr": "Ishpro Center", "lat": 31.8950, "lng": 34.9650},
            {"chain": "Rami Levy", "branch": "101", "name": "Rami Levy Modiin", "addr": "Ishpro Center", "lat": 31.8960, "lng": 34.9660},
            {"chain": "Victory", "branch": "201", "name": "Victory Modiin", "addr": "Lev HaIr", "lat": 31.9080, "lng": 35.0080},
        ]
        stores = {}
        for cfg in stores_config:
            s = db.query(Store).filter(Store.chain_id == chains[cfg["chain"]].id, Store.branch_id == cfg["branch"]).first()
            if not s:
                s = Store(
                    chain_id=chains[cfg["chain"]].id,
                    branch_id=cfg["branch"],
                    name=cfg["name"],
                    address=cfg["addr"],
                    location=from_shape(Point(cfg["lng"], cfg["lat"]), srid=4326)
                )
                db.add(s)
                db.commit()
                db.refresh(s)
            stores[cfg["name"]] = s

        # 3. Define Aggregates (Common denominators)
        aggregates_config = [
            {"name": "Milk 3% Regular", "unit": UnitOfMeasure.VOLUME}, # Base unit: Liter
            {"name": "Standard Cottage Cheese", "unit": UnitOfMeasure.MASS},   # Base unit: KG
            {"name": "Eggs Large", "unit": UnitOfMeasure.UNITS}, # Base unit: Single Egg
        ]
        aggregates = {}
        for cfg in aggregates_config:
            a = db.query(Aggregate).filter(Aggregate.user_id == user.id, Aggregate.name == cfg["name"]).first()
            if not a:
                a = Aggregate(
                    user_id=user.id,
                    name=cfg["name"],
                    unit_of_measure=cfg["unit"]
                )
                db.add(a)
                db.commit()
                db.refresh(a)
            aggregates[cfg["name"]] = a

        # 4. Create Items and Prices
        items_data = [
            # Milk (1 Liter)
            {
                "agg": "Milk 3% Regular", 
                "code": "7290000042458", 
                "name": "חלב תנובה 3% 1 ליטר", 
                "brand": "תנובה", 
                "qty": 1.0, 
                "prices": {"Shufersal Deal Modiin": 6.20, "Rami Levy Modiin": 6.10, "Victory Modiin": 6.30}
            },
            # Cottage (250 grams -> 0.25 KG)
            {
                "agg": "Standard Cottage Cheese", 
                "code": "7290000043110", 
                "name": "קוטג' תנובה 250 גרם", 
                "brand": "תנובה", 
                "qty": 0.25, 
                "prices": {"Shufersal Deal Modiin": 5.90, "Rami Levy Modiin": 5.70, "Victory Modiin": 6.10}
            },
            # Eggs (12 pack)
            {
                "agg": "Eggs Large", 
                "code": "7290000000001", 
                "name": "ביצים L 12 יחידות", 
                "brand": "Generic", 
                "qty": 12.0, 
                "prices": {"Shufersal Deal Modiin": 12.50, "Rami Levy Modiin": 12.20, "Victory Modiin": 12.80}
            },
        ]

        for data in items_data:
            for chain_name, chain in chains.items():
                item = db.query(Item).filter(Item.chain_id == chain.id, Item.item_code == data["code"]).first()
                if not item:
                    item = Item(
                        chain_id=chain.id,
                        item_code=data["code"],
                        name=data["name"],
                        brand=data["brand"],
                        unit_of_measure=aggregates[data["agg"]].unit_of_measure,
                        quantity=data["qty"]
                    )
                    db.add(item)
                    db.flush()
                
                # Link to Aggregate
                agg_item = db.query(AggregateItem).filter(AggregateItem.aggregate_id == aggregates[data["agg"]].id, AggregateItem.item_id == item.id).first()
                if not agg_item:
                    db.add(AggregateItem(aggregate_id=aggregates[data["agg"]].id, item_id=item.id))

                # Add Prices
                for store_name, price_val in data["prices"].items():
                    store = stores.get(store_name)
                    if store and store.chain_id == chain.id:
                        price = db.query(Price).filter(Price.item_id == item.id, Price.store_id == store.id).first()
                        if not price:
                            p_val = Decimal(str(price_val))
                            db.add(Price(
                                item_id=item.id,
                                store_id=store.id,
                                base_price=p_val,
                                effective_price=p_val,
                                price_per_unit=p_val / Decimal(str(data["qty"]))
                            ))

        db.commit()
        print("Seeding successful with normalized Modi'in mock data.")
    except Exception as e:
        print(f"Seeding error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
