"""
Shared domain types for basket optimization.

WantedItem  — one thing the user wants to buy, with all candidate prices across stores.
CandidatePrice — a specific SKU at a specific store that could satisfy a WantedItem.
AssignedItem   — the winning candidate chosen by the optimizer.
OptimizationResult — the optimizer's output: best store, assigned items, unresolved items.

Note: `unit` is stored as a plain str to avoid importing the ORM-coupled UnitOfMeasure
enum here. See candidate-5 in the architecture plan for the fix.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from uuid import UUID


@dataclass
class CandidatePrice:
    item_id: UUID
    item_code: str            # EAN/GTIN barcode — used for reliable site search
    item_name: str
    brand: str
    unit_of_measure: str      # "MASS" / "VOLUME" / "UNITS"
    store_id: UUID
    store_name: str
    chain_name: str
    distance_km: float
    price_per_unit: Decimal   # effective_price / package_quantity — used for ranking
    effective_price: Decimal  # price per package — used for cost calculation
    package_quantity: float   # kg or L per package


@dataclass
class WantedItem:
    name: str
    desired_amount: float
    unit: str                          # UnitOfMeasure value as str ("MASS"/"VOLUME"/"UNITS")
    candidates: List[CandidatePrice] = field(default_factory=list)
    aggregate_id: Optional[UUID] = None  # present when sourced from a real DB aggregate


@dataclass
class AssignedItem:
    name: str
    aggregate_id: Optional[UUID]
    item_id: UUID
    item_code: str              # EAN/GTIN barcode — for order automation search
    item_name: str
    brand: str
    unit_of_measure: str        # "MASS" / "VOLUME" / "UNITS"
    package_quantity: float     # kg/L per package — for display
    store_id: UUID
    price_per_unit: Decimal
    packages_needed: Decimal
    cost: Decimal


@dataclass
class AlternativeStore:
    store_id: UUID
    store_name: str
    chain_name: str
    total_cost: Decimal


@dataclass
class OptimizationResult:
    store_id: Optional[UUID]        # None only when every item is globally unresolved
    store_name: str
    chain_name: str
    distance_km: float
    assigned_items: List[AssignedItem]
    total_cost: Decimal
    unresolved: List[WantedItem]    # items with no candidate in the chosen store
    alternatives: List[AlternativeStore] = field(default_factory=list)
