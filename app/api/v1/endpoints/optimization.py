from typing import Any, List
from uuid import UUID
from decimal import Decimal, ROUND_UP
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Store, ShoppingList, ShoppingListEntry, Aggregate, Price, Item, AggregateItem, Chain
from app.schemas.optimization import OptimizationRequest, OptimizationResponse, StoreResult, AlternativeStore

router = APIRouter()


def _resolve_entry_key(entry: ShoppingListEntry) -> str:
    """Stable key for an entry — aggregate id or item id."""
    return str(entry.aggregate_id) if entry.aggregate_id else str(entry.item_id)


def _build_store_options(db: Session, candidate_stores, list_entries):
    """For each store and list entry, find the cheapest applicable item."""
    options = {}
    for store, chain in candidate_stores:
        agg_map = {}
        for entry in list_entries:
            key = _resolve_entry_key(entry)

            if entry.aggregate_id:
                cheapest = (
                    db.query(Price, Item)
                    .join(Item)
                    .join(AggregateItem, AggregateItem.item_id == Item.id)
                    .filter(
                        AggregateItem.aggregate_id == entry.aggregate_id,
                        Price.store_id == store.id,
                    )
                    .order_by(Price.price_per_unit)
                    .first()
                )
                label = entry.aggregate.name if entry.aggregate else key
            else:
                cheapest = (
                    db.query(Price, Item)
                    .join(Item)
                    .filter(
                        Item.id == entry.item_id,
                        Price.store_id == store.id,
                    )
                    .order_by(Price.price_per_unit)
                    .first()
                )
                label = entry.item.name if entry.item else key

            if cheapest:
                price, item = cheapest
                unit_qty = Decimal(str(item.quantity)) if item.quantity and item.quantity > 0 else Decimal("1")
                desired = Decimal(str(entry.desired_amount))
                packages_needed = (desired / unit_qty).quantize(Decimal("1"), rounding=ROUND_UP)
                cost = price.effective_price * packages_needed
                agg_map[key] = {
                    "aggregate_id": key,
                    "aggregate_name": label,
                    "item_id": str(item.id),
                    "item_name": item.name,
                    "brand": item.brand or "",
                    "unit_of_measure": item.unit_of_measure.value if item.unit_of_measure else "UNITS",
                    "package_quantity": float(item.quantity) if item.quantity else 1.0,
                    "price_per_unit": float(price.effective_price),
                    "desired_amount": float(packages_needed),
                    "cost": float(cost),
                }
        options[store.id] = {
            "store_name": store.name,
            "chain_name": chain.name,
            "aggregates": agg_map,
        }
    return options


def _full_basket_alternatives(store_options, n_entries, exclude_store_ids):
    """Return all stores that can cover the full basket, sorted by cost."""
    candidates = []
    for store_id, data in store_options.items():
        if store_id in exclude_store_ids:
            continue
        if len(data["aggregates"]) < n_entries:
            continue
        total = sum(Decimal(str(v["cost"])) for v in data["aggregates"].values())
        candidates.append(AlternativeStore(
            store_name=data["store_name"],
            chain_name=data["chain_name"],
            total_cost=total,
        ))
    candidates.sort(key=lambda x: x.total_cost)
    return candidates


@router.post("/", response_model=OptimizationResponse)
def optimize_basket(
    request: OptimizationRequest,
    db: Session = Depends(get_db),
) -> Any:
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == request.shopping_list_id).first()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    # Load entries with their optional relationships eagerly
    list_entries = (
        db.query(ShoppingListEntry)
        .filter(ShoppingListEntry.shopping_list_id == request.shopping_list_id)
        .all()
    )
    if not list_entries:
        raise HTTPException(status_code=400, detail="Shopping list has no entries")

    # Eagerly load aggregate/item for label resolution
    for entry in list_entries:
        _ = entry.aggregate
        _ = entry.item

    candidate_stores = db.query(Store, Chain).join(Chain).all()
    if not candidate_stores:
        raise HTTPException(status_code=404, detail="No stores in database")

    store_options = _build_store_options(db, candidate_stores, list_entries)
    n_entries = len(list_entries)

    if request.max_stores == 1:
        all_complete = _full_basket_alternatives(store_options, n_entries, exclude_store_ids=set())
        if not all_complete:
            raise HTTPException(
                status_code=404,
                detail="No single store carries all items in your list",
            )

        best = all_complete[0]
        best_store_id = next(
            sid for sid, d in store_options.items()
            if d["store_name"] == best.store_name and d["chain_name"] == best.chain_name
        )
        d = store_options[best_store_id]
        results = [StoreResult(
            store_id=best_store_id,
            store_name=d["store_name"],
            chain_name=d["chain_name"],
            distance_km=0.0,
            items=list(d["aggregates"].values()),
            total_cost=best.total_cost,
        )]
        alternatives = all_complete[1:3]
    else:
        remaining = {_resolve_entry_key(e) for e in list_entries}
        selected: list[UUID] = []
        results = []

        while remaining and len(selected) < request.max_stores:
            best_id = None
            best_score = Decimal("Infinity")

            for store_id, data in store_options.items():
                if store_id in selected:
                    continue
                covered = {aid for aid in data["aggregates"] if aid in remaining}
                if not covered:
                    continue
                cost = sum(Decimal(str(data["aggregates"][aid]["cost"])) for aid in covered)
                score = cost / len(covered)
                if score < best_score:
                    best_score = score
                    best_id = store_id

            if not best_id:
                break

            selected.append(best_id)
            d = store_options[best_id]
            covered = {aid for aid in d["aggregates"] if aid in remaining}
            remaining -= covered
            total = sum(Decimal(str(d["aggregates"][aid]["cost"])) for aid in covered)
            results.append(StoreResult(
                store_id=best_id,
                store_name=d["store_name"],
                chain_name=d["chain_name"],
                distance_km=0.0,
                items=[d["aggregates"][aid] for aid in covered],
                total_cost=total,
            ))

        alternatives = _full_basket_alternatives(store_options, n_entries, exclude_store_ids=set(selected))[:2]

    total_basket = sum(r.total_cost for r in results)
    total_savings = (alternatives[0].total_cost - total_basket) if alternatives else Decimal("0.0")

    return OptimizationResponse(
        selected_stores=results,
        total_basket_cost=total_basket,
        total_savings=total_savings,
        alternatives=alternatives,
    )
