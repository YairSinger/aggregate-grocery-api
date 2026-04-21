import re
from app.db.models import UnitOfMeasure

UNIT_MAP = {
    "ק\"ג": UnitOfMeasure.MASS,
    "גרם": UnitOfMeasure.MASS,
    "ליטר": UnitOfMeasure.VOLUME,
    "מ\"ל": UnitOfMeasure.VOLUME,
    "יחידה": UnitOfMeasure.UNITS,
    "מארז": UnitOfMeasure.UNITS,
}

# Conversion factors to base units (KG, L, Unit)
UNIT_CONVERSION = {
    "גרם": 0.001,
    "מ\"ל": 0.001,
    "ק\"ג": 1.0,
    "ליטר": 1.0,
    "יחידה": 1.0,
    "מארז": 1.0,
}

# UnitQty field: maps the XML's free-text quantity-unit to (UnitOfMeasure enum, factor_to_base_unit)
# Base units: kg for MASS, liter for VOLUME, unit for UNITS
# factor_to_base_unit converts from the XML quantity unit to the base unit
# e.g. "גרמים" -> MASS, factor=0.001  means: Quantity grams * 0.001 = qty in kg
UNIT_QTY_MAP: dict[str, tuple[UnitOfMeasure, float]] = {
    # Mass — grams
    "גרם":      (UnitOfMeasure.MASS,   0.001),
    "גרמים":    (UnitOfMeasure.MASS,   0.001),
    # Mass — kilograms
    "ק\"ג":     (UnitOfMeasure.MASS,   1.0),
    "קג":       (UnitOfMeasure.MASS,   1.0),
    "ק'ג":      (UnitOfMeasure.MASS,   1.0),
    "קילוגרם":  (UnitOfMeasure.MASS,   1.0),
    "קילוגרמים":(UnitOfMeasure.MASS,   1.0),
    # Volume — millilitres
    "מ\"ל":     (UnitOfMeasure.VOLUME, 0.001),
    "מל":       (UnitOfMeasure.VOLUME, 0.001),
    "מיליליטר": (UnitOfMeasure.VOLUME, 0.001),
    "מיליליטרים":(UnitOfMeasure.VOLUME,0.001),
    # Volume — litres
    "ליטר":     (UnitOfMeasure.VOLUME, 1.0),
    "ליטרים":   (UnitOfMeasure.VOLUME, 1.0),
    # Units / packages
    "יחידה":    (UnitOfMeasure.UNITS,  1.0),
    "יחידות":   (UnitOfMeasure.UNITS,  1.0),
    "מארז":     (UnitOfMeasure.UNITS,  1.0),
    "מארזים":   (UnitOfMeasure.UNITS,  1.0),
}


def get_unit_and_factor(unit_qty_str: str | None) -> tuple[UnitOfMeasure, float]:
    """Return (UnitOfMeasure enum, factor_to_base_unit) for a UnitQty string.
    Falls back to UNITS/1.0 when unrecognised."""
    if not unit_qty_str:
        return UnitOfMeasure.UNITS, 1.0
    key = unit_qty_str.strip()
    return UNIT_QTY_MAP.get(key, (UnitOfMeasure.UNITS, 1.0))


def normalize_hebrew_text(text: str) -> str:
    if not text:
        return ""
    # Remove non-alphanumeric characters but keep Hebrew and spaces
    text = re.sub(r'[^\u0590-\u05FFa-zA-Z0-9\s]', ' ', text)
    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_quantity(quantity_str: str, unit_str: str) -> float:
    try:
        qty = float(quantity_str)
        factor = UNIT_CONVERSION.get(unit_str, 1.0)
        return qty * factor
    except (ValueError, TypeError):
        return 1.0

def normalize_item_code(item_code: str) -> str:
    # Remove leading zeros and whitespace
    if not item_code:
        return ""
    return item_code.strip().lstrip('0')
