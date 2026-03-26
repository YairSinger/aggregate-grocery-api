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
