from decimal import Decimal
from typing import Dict, List
from app.db.models import Item, Price, Store, Chain
from app.pipeline.parser import GroceryParser

class DataProcessor:
    @staticmethod
    def process_store_prices(
        price_items: List[Dict], 
        promo_data: List[Dict], 
        store_id: str, 
        chain_id: str
    ) -> List[Dict]:
        """
        Merge items and promotions to calculate effective prices for a specific store.
        """
        # Create a lookup for promotions by ItemCode
        item_promos = {}
        for promo in promo_data:
            for item_code in promo["items"]:
                # Simple logic: pick the first available discount
                if item_code not in item_promos:
                    item_promos[item_code] = promo

        processed_data = []
        for item in price_items:
            item_code = item["item_code"]
            base_price = item["price"]
            promo = item_promos.get(item_code)
            
            effective_price = base_price
            discount_price = None
            discount_desc = None
            
            if promo:
                try:
                    # MVP: Assume threshold met if discounted_price exists
                    d_price = Decimal(promo["discount_price"] or "0")
                    if d_price > 0 and d_price < base_price:
                        effective_price = d_price
                        discount_price = d_price
                        discount_desc = promo["description"]
                except:
                    pass
            
            # price_per_unit is in canonical base units:
            #   MASS   → ₪/kg   (normalized_quantity is in kg)
            #   VOLUME → ₪/litre (normalized_quantity is in litres)
            #   UNITS  → ₪/unit  (normalized_quantity is the item count)
            qty = Decimal(str(item["normalized_quantity"] or "1.0"))
            price_per_unit = effective_price / qty if qty > 0 else effective_price

            # Skip clearly bad items (e.g. normalization produced near-zero qty)
            MAX_PRICE_PER_UNIT = Decimal("99999999")
            if price_per_unit > MAX_PRICE_PER_UNIT or effective_price <= 0:
                continue

            processed_data.append({
                "item": {
                    "chain_id": chain_id,
                    "item_code": item_code,
                    "name": item["name"],
                    "brand": item["brand"],
                    "category": item["category"],
                    "unit_of_measure": item["unit_of_measure"],
                    "quantity": item["normalized_quantity"],
                },
                "price": {
                    "base_price": base_price,
                    "discount_price": discount_price,
                    "effective_price": effective_price,
                    "discount_description": discount_desc,
                    "price_per_unit": price_per_unit,
                }
            })
            
        return processed_data
