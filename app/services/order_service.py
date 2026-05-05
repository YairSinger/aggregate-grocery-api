"""
Order service — creates and manages Order/OrderItem/PendingItem records.

Keeps shufersal_order.py pure (no DB access). The FastAPI endpoint:
  1. Calls create_order() → gets order_id
  2. Submits build_cart_and_update(order_id, ...) to thread pool
  3. Returns 202 immediately with order_id

Background thread calls update_order_cart_built() or update_order_failed()
when the Playwright session finishes.

User then places the order manually and calls store_confirmation().
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import (
    Order,
    OrderItem,
    OrderStatus,
    PendingItem,
    PendingItemStatus,
)
from app.services.order_automation.shufersal_order import CartResult
from app.services.types import AssignedItem


# ---------------------------------------------------------------------------
# Order lifecycle

def create_order(
    db: Session,
    user_id: UUID,
    assigned_items: List[AssignedItem],
    store_name: str,
    chain_name: str,
    total_cost: float,
    store_id: Optional[UUID] = None,
    baseline_cost: Optional[float] = None,
    delivery_window_start: Optional[str] = None,
    delivery_window_end: Optional[str] = None,
) -> Order:
    """
    Create an Order + OrderItems from the optimizer result.
    Status starts as PENDING — transitions to CART_BUILDING when
    build_cart_and_update() is submitted to the thread pool.
    """
    order = Order(
        user_id=user_id,
        store_id=store_id,
        store_name=store_name,
        chain_name=chain_name,
        total_cost=total_cost,
        baseline_cost=baseline_cost,
        delivery_window_start=delivery_window_start,
        delivery_window_end=delivery_window_end,
        status=OrderStatus.PENDING,
    )
    db.add(order)
    db.flush()  # get order.id before adding items

    for item in assigned_items:
        db.add(OrderItem(
            order_id=order.id,
            item_id=item.item_id,
            aggregate_id=item.aggregate_id,
            item_code=item.item_code,
            item_name=item.item_name,
            aggregate_name=item.name,
            brand=item.brand,
            unit_of_measure=item.unit_of_measure,
            package_quantity=item.package_quantity,
            qty_packages=int(item.packages_needed),
            unit_price=item.price_per_unit,
            cost=item.cost,
        ))

    db.commit()
    db.refresh(order)
    return order


def update_order_cart_building(db: Session, order_id: UUID) -> None:
    """Mark order as cart-building (automation started)."""
    _set_status(db, order_id, OrderStatus.CART_BUILDING)


def update_order_cart_built(db: Session, order_id: UUID, cart_result: CartResult) -> Order:
    """
    Called by the background thread when build_cart() succeeds.
    Stores cart_url and screenshot path, transitions to AWAITING_CONFIRMATION.
    """
    order = _get_or_raise(db, order_id)
    order.cart_url = cart_result.cart_url
    order.cart_screenshot_path = cart_result.screenshot_path
    order.delivery_date = cart_result.delivery_date
    order.status = OrderStatus.AWAITING_CONFIRMATION
    db.commit()
    db.refresh(order)
    return order


def update_order_failed(db: Session, order_id: UUID, error: str) -> None:
    """Called by the background thread when build_cart() raises."""
    order = _get_or_raise(db, order_id)
    order.status = OrderStatus.FAILED
    order.error_message = error
    db.commit()


def store_confirmation(
    db: Session, order_id: UUID, confirmation_number: str
) -> Order:
    """
    Called when user replies with confirmation number in Telegram.
    OpenClaw calls the MCP tool store_confirmation(order_id, number).
    """
    order = _get_or_raise(db, order_id)
    if order.status != OrderStatus.AWAITING_CONFIRMATION:
        raise ValueError(
            f"Order {order_id} is in status {order.status.value}, "
            "expected awaiting_confirmation"
        )
    order.confirmation_number = confirmation_number
    order.status = OrderStatus.PLACED
    order.placed_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: UUID) -> Order:
    return _get_or_raise(db, order_id)


# ---------------------------------------------------------------------------
# Background task — runs in thread pool, opens its own DB session

def build_cart_and_update(
    order_id: UUID,
    assigned_items: List[AssignedItem],
    delivery_window_start: str,
    delivery_window_end: str,
) -> None:
    """
    Meant to run in a thread pool executor (not in the FastAPI event loop).
    Opens its own DB session. Calls build_cart(), then updates the Order.

    Usage from FastAPI:
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(
            loop.run_in_executor(None, build_cart_and_update, order_id, items, ws, we)
        )
    """
    from app.db.session import SessionLocal
    from app.services.order_automation.shufersal_order import build_cart, ShufersalCredentials

    db = SessionLocal()
    try:
        update_order_cart_building(db, order_id)
        creds = ShufersalCredentials.from_env()
        cart_result = build_cart(
            items=assigned_items,
            preferred_window_start=delivery_window_start,
            preferred_window_end=delivery_window_end,
            credentials=creds,
        )
        update_order_cart_built(db, order_id, cart_result)
    except Exception as exc:
        try:
            update_order_failed(db, order_id, str(exc))
        except Exception:
            pass
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pending items

def add_pending_item(
    db: Session,
    user_id: UUID,
    item_name: str,
    qty: float = 1.0,
    unit: str = "UNITS",
    aggregate_id: Optional[UUID] = None,
) -> PendingItem:
    item = PendingItem(
        user_id=user_id,
        item_name=item_name,
        qty=qty,
        unit=unit,
        aggregate_id=aggregate_id,
        status=PendingItemStatus.PENDING,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_pending_items(db: Session, user_id: UUID) -> List[PendingItem]:
    """Return all pending + skipped items for the user (skipped = carried from last week)."""
    return (
        db.query(PendingItem)
        .filter(
            PendingItem.user_id == user_id,
            PendingItem.status.in_([PendingItemStatus.PENDING, PendingItemStatus.SKIPPED]),
        )
        .order_by(PendingItem.added_at)
        .all()
    )


def skip_pending_items(db: Session, item_ids: List[UUID]) -> None:
    db.query(PendingItem).filter(PendingItem.id.in_(item_ids)).update(
        {"status": PendingItemStatus.SKIPPED}, synchronize_session=False
    )
    db.commit()


def mark_pending_items_ordered(db: Session, user_id: UUID, order_id: UUID) -> None:
    """Called after order is confirmed — marks all pending items as ordered."""
    db.query(PendingItem).filter(
        PendingItem.user_id == user_id,
        PendingItem.status == PendingItemStatus.PENDING,
    ).update(
        {"status": PendingItemStatus.ORDERED, "order_id": order_id},
        synchronize_session=False,
    )
    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers

def _get_or_raise(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise ValueError(f"Order {order_id} not found")
    return order


def _set_status(db: Session, order_id: UUID, status: OrderStatus) -> None:
    order = _get_or_raise(db, order_id)
    order.status = status
    db.commit()
