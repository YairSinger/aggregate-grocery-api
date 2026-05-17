"""
Pending items loader — PendingItem rows → List[WantedItem].

Used by optimize_cart() MCP tool. Items without aggregate_id are returned
with empty candidates — optimizer marks them unresolved.
Stores with NULL location are always included (no coordinates → can't filter by distance).
"""

from typing import List
from uuid import UUID

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    Aggregate, AggregateItem, Chain, Item,
    PendingItem, PendingItemStatus, Price, Store,
)
from app.services.loaders.shopping_list_loader import _make_candidate
from app.services.types import WantedItem


def load_wanted_items_from_pending(
    db: Session,
    user_id: UUID,
    user_lat: float,
    user_lng: float,
    max_distance_km: float = 5.0,
) -> List[WantedItem]:
    pending = (
        db.query(PendingItem)
        .filter(
            PendingItem.user_id == user_id,
            PendingItem.status == PendingItemStatus.PENDING,
        )
        .all()
    )
    if not pending:
        return []

    user_point = from_shape(Point(user_lng, user_lat), srid=4326)
    max_dist_m = max_distance_km * 1000

    unmatched = [p for p in pending if p.aggregate_id is None]
    matched = [p for p in pending if p.aggregate_id is not None]
    agg_to_pending: dict = {p.aggregate_id: p for p in matched}

    wanted: dict = {}

    if matched:
        rows = (
            db.query(
                Aggregate.id.label("aggregate_id"),
                Aggregate.name.label("aggregate_name"),
                Aggregate.unit_of_measure,
                Item.id.label("item_id"),
                Item.name.label("item_name"),
                Item.item_code.label("item_code"),
                Item.brand.label("brand"),
                Item.unit_of_measure.label("item_unit"),
                Item.quantity.label("pkg_qty"),
                Price.effective_price,
                Price.price_per_unit,
                Store.id.label("store_id"),
                Store.name.label("store_name"),
                Chain.name.label("chain_name"),
                (func.ST_Distance(Store.location, user_point) / 1000).label("distance_km"),
            )
            .select_from(Aggregate)
            .join(AggregateItem, AggregateItem.aggregate_id == Aggregate.id)
            .join(Item, Item.id == AggregateItem.item_id)
            .join(Price, Price.item_id == Item.id)
            .join(Store, Store.id == Price.store_id)
            .join(Chain, Chain.id == Store.chain_id)
            .filter(
                Aggregate.id.in_(list(agg_to_pending.keys())),
                or_(
                    Store.location.is_(None),
                    func.ST_DWithin(Store.location, user_point, max_dist_m),
                ),
            )
            .all()
        )

        for row in rows:
            if row.aggregate_id not in wanted:
                p = agg_to_pending[row.aggregate_id]
                wanted[row.aggregate_id] = WantedItem(
                    name=row.aggregate_name,
                    desired_amount=float(p.qty),
                    unit=row.unit_of_measure.value if row.unit_of_measure else "UNITS",
                    aggregate_id=row.aggregate_id,
                    candidates=[],
                )
            wanted[row.aggregate_id].candidates.append(_make_candidate(row))

        for agg_id, p in agg_to_pending.items():
            if agg_id not in wanted:
                agg = db.query(Aggregate).filter(Aggregate.id == agg_id).first()
                wanted[agg_id] = WantedItem(
                    name=agg.name if agg else p.item_name,
                    desired_amount=float(p.qty),
                    unit=agg.unit_of_measure.value if agg and agg.unit_of_measure else "UNITS",
                    aggregate_id=agg_id,
                    candidates=[],
                )

    result = list(wanted.values())
    for p in unmatched:
        result.append(WantedItem(
            name=p.item_name,
            desired_amount=float(p.qty),
            unit=p.unit,
            aggregate_id=None,
            candidates=[],
        ))
    return result
