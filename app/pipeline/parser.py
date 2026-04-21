from lxml import etree
from decimal import Decimal
from typing import Dict, List, Optional
from app.db.models import UnitOfMeasure
from app.pipeline.utils import UNIT_MAP, parse_quantity, normalize_item_code, normalize_hebrew_text, get_unit_and_factor

class GroceryParser:
    @staticmethod
    def parse_price_file(file_path: str) -> List[Dict]:
        items = []
        context = etree.iterparse(file_path, events=('end',), tag='Item')
        for event, elem in context:
            # UnitQty is the reliable per-chain field describing the unit of the Quantity value
            # e.g. "גרמים" for grams, "ליטרים" for litres, "יחידה" for units
            unit_qty_str = (elem.findtext('UnitQty') or '').strip()
            quantity_str = elem.findtext('Quantity') or '1'
            price = Decimal(elem.findtext('ItemPrice') or "0")

            unit_of_measure, factor = get_unit_and_factor(unit_qty_str)

            try:
                raw_qty = float(quantity_str)
            except (ValueError, TypeError):
                raw_qty = 1.0

            # quantity_in_base: kg for MASS, litres for VOLUME, count for UNITS
            quantity_in_base = raw_qty * factor if raw_qty > 0 else 1.0

            item_data = {
                "item_code": normalize_item_code(elem.findtext('ItemCode')),
                "name": normalize_hebrew_text(elem.findtext('ItemName')),
                "brand": normalize_hebrew_text(elem.findtext('ManufacturerName')),
                "category": normalize_hebrew_text(elem.findtext('CategoryName')),
                "unit_of_measure": unit_of_measure,
                # Store the raw quantity (grams/ml/units) for display; base-unit quantity used for pricing
                "quantity": raw_qty,
                "normalized_quantity": quantity_in_base,
                "price": price,
            }

            items.append(item_data)
            # Clear element from memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return items

    @staticmethod
    def parse_promo_file(file_path: str) -> List[Dict]:
        promos = []
        context = etree.iterparse(file_path, events=('end',), tag='Promotion')
        for event, elem in context:
            promo_data = {
                "promo_id": elem.findtext('PromotionId'),
                "description": normalize_hebrew_text(elem.findtext('PromotionDescription')),
                "discount_price": elem.findtext('DiscountedPrice'),
                "min_qty": elem.findtext('MinQty'),
                "max_qty": elem.findtext('MaxQty'),
                "min_purchase": elem.findtext('MinPurchasePrice'),
                "items": [normalize_item_code(i.findtext('ItemCode')) for i in elem.xpath('.//Item')],
            }
            promos.append(promo_data)
            # Clear memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return promos

    @staticmethod
    def parse_store_file(file_path: str, city_filter: str = None) -> List[Dict]:
        stores = []
        # Hebrew 'Modiin' can be represented in different ways, we'll check for the substring
        city_filter_norm = normalize_hebrew_text(city_filter) if city_filter else None
        
        context = etree.iterparse(file_path, events=('end',), tag='Store')
        for event, elem in context:
            branch_id = elem.findtext('StoreId')
            name = normalize_hebrew_text(elem.findtext('StoreName'))
            address = normalize_hebrew_text(elem.findtext('Address'))
            city = normalize_hebrew_text(elem.findtext('City'))
            
            # Filter by city if provided
            if city_filter_norm:
                if city_filter_norm not in city or city_filter_norm not in address:
                    # Double check name too
                    if city_filter_norm not in name:
                        elem.clear()
                        continue

            store_data = {
                "branch_id": branch_id,
                "name": name,
                "address": address,
                "city": city,
                "lat": elem.findtext('Latitude'),
                "lng": elem.findtext('Longitude'),
            }
            stores.append(store_data)
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        return stores
