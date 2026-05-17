"""
Agent endpoints — the MCP server calls these.
All use X-User-Email header auth. Designed for machine callers.

  POST/GET /agent/pending-items         add_pending_item / get_pending_items
  POST     /agent/pending-items/skip    skip_items
  GET      /agent/aggregates            list_aggregates
  POST     /agent/aggregates/ensure     ensure_aggregate
  DELETE   /agent/aggregates/{id}/items/{id}  remove_item_from_aggregate
  POST     /agent/optimize              optimize_cart → creates Order
  POST     /agent/orders/{id}/build-cart  confirm_order (triggers Playwright, 202)
  GET      /agent/orders/{id}           get_order_status
  POST     /agent/orders/{id}/confirm   store_confirmation
"""

import asyncio
from decimal import Decimal
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import Aggregate, AggregateItem, Item, User
from app.services import order_service
from app.services.basket_optimizer import optimize_single_store
from app.services.loaders.pending_items_loader import load_wanted_items_from_pending

router = APIRouter()

_DEFAULT_LAT = 32.0853
_DEFAULT_LNG = 34.7818


# ---------------------------------------------------------------------------
# Schemas

class AddPendingItemRequest(BaseModel):
    item_name: str
    qty: float = 1.0
    unit: str = "UNITS"
    aggregate_id: Optional[UUID] = None


class SkipItemsRequest(BaseModel):
    item_ids: List[UUID]


class EnsureAggregateRequest(BaseModel):
    name: str
    unit_of_measure: str = "UNITS"
    search_hint: Optional[str] = None


class OptimizeCartRequest(BaseModel):
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None
    max_distance_km: float = 5.0


class BuildCartRequest(BaseModel):
    delivery_window_start: str
    delivery_window_end: str


class StoreConfirmationRequest(BaseModel):
    confirmation_number: str


# ---------------------------------------------------------------------------
# Pending items

@router.post("/pending-items", status_code=201)
def add_pending_item(
    body: AddPendingItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    item = order_service.add_pending_item(
        db=db,
        user_id=current_user.id,
        item_name=body.item_name,
        qty=body.qty,
        unit=body.unit,
        aggregate_id=body.aggregate_id,
    )
    return {
        "id": str(item.id),
        "item_name": item.item_name,
        "qty": item.qty,
        "unit": item.unit,
        "aggregate_id": str(item.aggregate_id) if item.aggregate_id else None,
        "status": item.status.value,
        "added_at": item.added_at.isoformat(),
    }


@router.get("/pending-items")
def get_pending_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    items = order_service.get_pending_items(db, current_user.id)
    return {
        "items": [
            {
                "id": str(i.id),
                "item_name": i.item_name,
                "qty": i.qty,
                "unit": i.unit,
                "aggregate_id": str(i.aggregate_id) if i.aggregate_id else None,
                "aggregate_name": i.aggregate.name if i.aggregate else None,
                "status": i.status.value,
                "added_at": i.added_at.isoformat(),
            }
            for i in items
        ],
        "total": len(items),
        "unmatched": sum(1 for i in items if i.aggregate_id is None),
    }


@router.post("/pending-items/skip")
def skip_items(
    body: SkipItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    order_service.skip_pending_items(db, body.item_ids)
    return {"skipped": len(body.item_ids)}


# ---------------------------------------------------------------------------
# Aggregate management

@router.get("/aggregates")
def list_aggregates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    aggs = db.query(Aggregate).filter(Aggregate.user_id == current_user.id).all()
    return {
        "aggregates": [
            {
                "id": str(a.id),
                "name": a.name,
                "unit_of_measure": a.unit_of_measure.value if a.unit_of_measure else None,
                "item_count": len(a.items),
            }
            for a in aggs
        ]
    }


@router.post("/aggregates/ensure", status_code=201)
def ensure_aggregate(
    body: EnsureAggregateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Find aggregate by name (case-insensitive) or create it, auto-linking catalog items."""
    from app.db.models import UnitOfMeasure

    existing = (
        db.query(Aggregate)
        .filter(Aggregate.user_id == current_user.id, Aggregate.name.ilike(body.name))
        .first()
    )
    if existing:
        return {"id": str(existing.id), "name": existing.name, "created": False}

    try:
        unit = UnitOfMeasure(body.unit_of_measure.upper())
    except ValueError:
        unit = UnitOfMeasure.UNITS

    agg = Aggregate(user_id=current_user.id, name=body.name, unit_of_measure=unit)
    db.add(agg)
    db.flush()

    search_term = body.search_hint or body.name
    catalog_items = db.query(Item).filter(Item.name.ilike(f"%{search_term}%")).limit(5).all()
    linked_items = []
    for item in catalog_items:
        db.add(AggregateItem(aggregate_id=agg.id, item_id=item.id))
        linked_items.append(item.name)

    db.commit()
    db.refresh(agg)
    return {
        "id": str(agg.id),
        "name": agg.name,
        "unit_of_measure": agg.unit_of_measure.value,
        "created": True,
        "items_linked": linked_items,
    }


@router.delete("/aggregates/{aggregate_id}/items/{item_id}")
def remove_item_from_aggregate(
    aggregate_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    agg = db.query(Aggregate).filter(
        Aggregate.id == aggregate_id, Aggregate.user_id == current_user.id
    ).first()
    if not agg:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    link = db.query(AggregateItem).filter(
        AggregateItem.aggregate_id == aggregate_id, AggregateItem.item_id == item_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Item not in aggregate")
    db.delete(link)
    db.commit()
    return {"removed": True}


# ---------------------------------------------------------------------------
# Optimization

@router.post("/optimize")
def optimize_cart(
    body: OptimizeCartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Optimize pending items, create Order record, return full preview + unresolved."""
    user_lat = body.user_lat or _DEFAULT_LAT
    user_lng = body.user_lng or _DEFAULT_LNG

    wanted = load_wanted_items_from_pending(
        db=db, user_id=current_user.id,
        user_lat=user_lat, user_lng=user_lng,
        max_distance_km=body.max_distance_km,
    )
    if not wanted:
        raise HTTPException(status_code=400, detail="No pending items to optimize")

    result = optimize_single_store(wanted)
    if result.store_id is None:
        raise HTTPException(status_code=404, detail="No nearby store has any of the pending items")

    order = order_service.create_order(
        db=db,
        user_id=current_user.id,
        assigned_items=result.assigned_items,
        store_name=result.store_name,
        chain_name=result.chain_name,
        total_cost=float(result.total_cost),
        store_id=result.store_id,
    )

    return {
        "order_id": str(order.id),
        "store_name": result.store_name,
        "chain_name": result.chain_name,
        "distance_km": result.distance_km,
        "total_cost": float(result.total_cost),
        "savings_vs_next": float(
            result.alternatives[0].total_cost - result.total_cost
        ) if result.alternatives else 0.0,
        "items": [
            {
                "aggregate_name": i.name,
                "item_name": i.item_name,
                "brand": i.brand,
                "unit_of_measure": i.unit_of_measure,
                "package_quantity": i.package_quantity,
                "item_code": i.item_code,
                "packages": int(i.packages_needed),
                "unit_price": float(i.price_per_unit),
                "cost": float(i.cost),
            }
            for i in result.assigned_items
        ],
        "unresolved": [
            {"name": w.name, "qty": w.desired_amount, "unit": w.unit}
            for w in result.unresolved
        ],
        "alternatives": [
            {"store_name": a.store_name, "chain": a.chain_name, "total_cost": float(a.total_cost)}
            for a in result.alternatives[:2]
        ],
    }


# ---------------------------------------------------------------------------
# Order lifecycle

@router.post("/orders/{order_id}/build-cart", status_code=202)
async def confirm_order(
    order_id: UUID,
    body: BuildCartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Trigger Playwright cart-building in background thread. Returns 202 immediately."""
    order = order_service.get_order(db, order_id)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    assigned = _order_items_to_assigned(order.items)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, order_service.build_cart_and_update,
        order_id, assigned, body.delivery_window_start, body.delivery_window_end,
    )
    return {"order_id": str(order_id), "status": "cart_building",
            "message": "Cart building started. Poll /agent/orders/{id} for status."}


@router.get("/orders/{order_id}")
def get_order_status(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    order = order_service.get_order(db, order_id)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    return {
        "order_id": str(order.id),
        "status": order.status.value,
        "store_name": order.store_name,
        "chain_name": order.chain_name,
        "total_cost": float(order.total_cost),
        "cart_url": order.cart_url,
        "delivery_date": order.delivery_date,
        "confirmation_number": order.confirmation_number,
        "error": order.error_message,
        "created_at": order.created_at.isoformat(),
        "placed_at": order.placed_at.isoformat() if order.placed_at else None,
        "items": [
            {
                "item_name": i.item_name,
                "aggregate_name": i.aggregate_name,
                "brand": i.brand,
                "qty_packages": i.qty_packages,
                "unit_price": float(i.unit_price),
                "cost": float(i.cost),
            }
            for i in order.items
        ],
    }


@router.post("/orders/{order_id}/confirm")
def store_confirmation(
    order_id: UUID,
    body: StoreConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    order = order_service.get_order(db, order_id)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your order")
    try:
        order = order_service.store_confirmation(db, order_id, body.confirmation_number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    order_service.mark_pending_items_ordered(db, current_user.id, order_id)
    return {
        "order_id": str(order.id),
        "status": order.status.value,
        "confirmation_number": order.confirmation_number,
        "placed_at": order.placed_at.isoformat(),
    }


# ---------------------------------------------------------------------------

def _order_items_to_assigned(order_items):
    from app.services.types import AssignedItem
    return [
        AssignedItem(
            name=oi.aggregate_name or oi.item_name,
            aggregate_id=oi.aggregate_id,
            item_id=oi.item_id,
            item_code=oi.item_code,
            item_name=oi.item_name,
            brand=oi.brand or "",
            unit_of_measure=oi.unit_of_measure or "UNITS",
            package_quantity=float(oi.package_quantity or 1.0),
            store_id=None,
            price_per_unit=Decimal(str(oi.unit_price)),
            packages_needed=Decimal(str(oi.qty_packages)),
            cost=Decimal(str(oi.cost)),
        )
        for oi in order_items
    ]
