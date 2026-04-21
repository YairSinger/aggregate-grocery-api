from typing import Any, List
from uuid import UUID
from decimal import Decimal, ROUND_UP
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Store, ShoppingList, ShoppingListEntry, Aggregate, Price, Item, AggregateItem, Chain
from app.schemas.optimization import OptimizationRequest, OptimizationResponse, StoreResult

router = APIRouter()


def _build_store_options(db: Session, candidate_stores, list_entries):
    """For each store and aggregate entry, find the cheapest item. Returns nested dict."""
    options = {}
    for store, chain in candidate_stores:
        agg_map = {}
        for entry, aggregate in list_entries:
            cheapest = (
                db.query(Price, Item)
                .join(Item)
                .join(AggregateItem, AggregateItem.item_id == Item.id)
                .filter(
                    AggregateItem.aggregate_id == aggregate.id,
                    Price.store_id == store.id,
                )
                .order_by(Price.price_per_unit)
                .first()
            )
            if cheapest:
                price, item = cheapest
                unit_qty = Decimal(str(item.quantity)) if item.quantity and item.quantity > 0 else Decimal("1")
                desired = Decimal(str(entry.desired_amount))
                packages_needed = (desired / unit_qty).quantize(Decimal("1"), rounding=ROUND_UP)
                cost = price.effective_price * packages_needed
                agg_map[aggregate.id] = {
                    "aggregate_id": str(aggregate.id),
                    "aggregate_name": aggregate.name,
                    "item_id": str(item.id),
                    "item_name": item.name,
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


@router.post("/", response_model=OptimizationResponse)
def optimize_basket(
    request: OptimizationRequest,
    db: Session = Depends(get_db),
) -> Any:
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == request.shopping_list_id).first()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")

    list_entries = (
        db.query(ShoppingListEntry, Aggregate)
        .join(Aggregate)
        .filter(ShoppingListEntry.shopping_list_id == request.shopping_list_id)
        .all()
    )
    if not list_entries:
        raise HTTPException(status_code=400, detail="Shopping list has no entries")

    candidate_stores = db.query(Store, Chain).join(Chain).all()
    if not candidate_stores:
        raise HTTPException(status_code=404, detail="No stores in database")

    store_options = _build_store_options(db, candidate_stores, list_entries)
    n_aggregates = len(list_entries)

    if request.max_stores == 1:
        best_store_id = None
        min_total = Decimal("Infinity")
        for store_id, data in store_options.items():
            if len(data["aggregates"]) < n_aggregates:
                continue
            total = sum(Decimal(str(v["cost"])) for v in data["aggregates"].values())
            if total < min_total:
                min_total = total
                best_store_id = store_id

        if not best_store_id:
            raise HTTPException(
                status_code=404,
                detail="No single store carries all items in your list",
            )
        d = store_options[best_store_id]
        results = [StoreResult(
            store_id=best_store_id,
            store_name=d["store_name"],
            chain_name=d["chain_name"],
            distance_km=0.0,
            items=list(d["aggregates"].values()),
            total_cost=min_total,
        )]
    else:
        # Greedy multi-store
        remaining = {agg.id for _, agg in list_entries}
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

    total_basket = sum(r.total_cost for r in results)
    return OptimizationResponse(
        selected_stores=results,
        total_basket_cost=total_basket,
        total_savings=Decimal("0.0"),
    )
