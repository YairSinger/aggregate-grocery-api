"""
Shopping list loader — DB → List[WantedItem].

Replaces the N×M query loop in the old optimization endpoint with two
bulk queries (one for aggregate-backed entries, one for direct-item entries),
then merges them in Python.

Also fixes the broken ST_Distance N+1: distance is computed in-query via
ST_Distance, once per (entry, store) row, not in a Python loop.
"""

from decimal import Decimal
from typing import List
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    Aggregate,
    AggregateItem,
    Chain,
    Item,
    Price,
    ShoppingList,
    ShoppingListEntry,
    Store,
)
from app.services.types import CandidatePrice, WantedItem


def load_wanted_items(
    db: Session,
    shopping_list_id: UUID,
    user_lat: float,
    user_lng: float,
    max_distance_km: float = 5.0,
) -> List[WantedItem]:
    """
    Load all WantedItems for a shopping list, with CandidatePrices pre-fetched
    for every nearby store in a single bulk query per entry type.

    Raises ValueError if the shopping list does not exist or has no entries.
    """
    shopping_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.id == shopping_list_id)
        .first()
    )
    if not shopping_list:
        raise ValueError(f"Shopping list {shopping_list_id} not found")

    user_point = from_shape(Point(user_lng, user_lat), srid=4326)
    max_dist_m = max_distance_km * 1000

    wanted: dict[UUID, WantedItem] = {}

    # --- aggregate-backed entries -------------------------------------------
    agg_rows = (
        db.query(
            ShoppingListEntry.id.label("entry_id"),
            ShoppingListEntry.aggregate_id,
            ShoppingListEntry.desired_amount,
            Aggregate.name.label("aggregate_name"),
            Aggregate.unit_of_measure,
            Item.id.label("item_id"),
            Item.name.label("item_name"),
            Item.quantity.label("pkg_qty"),
            Price.effective_price,
            Price.price_per_unit,
            Store.id.label("store_id"),
            Store.name.label("store_name"),
            Chain.name.label("chain_name"),
            (func.ST_Distance(Store.location, user_point) / 1000).label("distance_km"),
        )
        .select_from(ShoppingListEntry)
        .join(Aggregate, Aggregate.id == ShoppingListEntry.aggregate_id)
        .join(AggregateItem, AggregateItem.aggregate_id == Aggregate.id)
        .join(Item, Item.id == AggregateItem.item_id)
        .join(Price, Price.item_id == Item.id)
        .join(Store, Store.id == Price.store_id)
        .join(Chain, Chain.id == Store.chain_id)
        .filter(
            ShoppingListEntry.shopping_list_id == shopping_list_id,
            ShoppingListEntry.aggregate_id.isnot(None),
            func.ST_DWithin(Store.location, user_point, max_dist_m),
        )
        .all()
    )

    for row in agg_rows:
        if row.entry_id not in wanted:
            wanted[row.entry_id] = WantedItem(
                name=row.aggregate_name,
                desired_amount=float(row.desired_amount),
                unit=row.unit_of_measure.value if row.unit_of_measure else "UNITS",
                aggregate_id=row.aggregate_id,
                candidates=[],
            )
        wanted[row.entry_id].candidates.append(_make_candidate(row))

    # --- direct-item entries -------------------------------------------------
    item_rows = (
        db.query(
            ShoppingListEntry.id.label("entry_id"),
            ShoppingListEntry.desired_amount,
            Item.id.label("item_id"),
            Item.name.label("item_name"),
            Item.quantity.label("pkg_qty"),
            Item.unit_of_measure,
            Price.effective_price,
            Price.price_per_unit,
            Store.id.label("store_id"),
            Store.name.label("store_name"),
            Chain.name.label("chain_name"),
            (func.ST_Distance(Store.location, user_point) / 1000).label("distance_km"),
        )
        .select_from(ShoppingListEntry)
        .join(Item, Item.id == ShoppingListEntry.item_id)
        .join(Price, Price.item_id == Item.id)
        .join(Store, Store.id == Price.store_id)
        .join(Chain, Chain.id == Store.chain_id)
        .filter(
            ShoppingListEntry.shopping_list_id == shopping_list_id,
            ShoppingListEntry.item_id.isnot(None),
            func.ST_DWithin(Store.location, user_point, max_dist_m),
        )
        .all()
    )

    for row in item_rows:
        if row.entry_id not in wanted:
            wanted[row.entry_id] = WantedItem(
                name=row.item_name,
                desired_amount=float(row.desired_amount),
                unit=row.unit_of_measure.value if row.unit_of_measure else "UNITS",
                aggregate_id=None,
                candidates=[],
            )
        wanted[row.entry_id].candidates.append(_make_candidate(row))

    # entries with no nearby-store prices end up with empty candidates —
    # the optimizer handles them as unresolved.
    result = list(wanted.values())

    # also include entries that had zero price rows (no nearby store at all)
    all_entry_ids = {
        e.id
        for e in db.query(ShoppingListEntry.id)
        .filter(ShoppingListEntry.shopping_list_id == shopping_list_id)
        .all()
    }
    missing_ids = all_entry_ids - set(wanted.keys())
    if missing_ids:
        missing_entries = (
            db.query(ShoppingListEntry)
            .filter(ShoppingListEntry.id.in_(missing_ids))
            .all()
        )
        for entry in missing_entries:
            name = (
                entry.aggregate.name
                if entry.aggregate
                else (entry.item.name if entry.item else str(entry.id))
            )
            result.append(WantedItem(
                name=name,
                desired_amount=float(entry.desired_amount),
                unit="UNITS",
                aggregate_id=entry.aggregate_id,
                candidates=[],
            ))

    if not result:
        raise ValueError(f"Shopping list {shopping_list_id} has no entries")

    return result


# ---------------------------------------------------------------------------

def _make_candidate(row) -> CandidatePrice:
    pkg_qty = float(row.pkg_qty) if row.pkg_qty and row.pkg_qty > 0 else 1.0
    return CandidatePrice(
        item_id=row.item_id,
        item_name=row.item_name,
        store_id=row.store_id,
        store_name=row.store_name,
        chain_name=row.chain_name,
        distance_km=float(row.distance_km or 0.0),
        price_per_unit=Decimal(str(row.price_per_unit)),
        effective_price=Decimal(str(row.effective_price)),
        package_quantity=pkg_qty,
    )
