from typing import Any, List, Dict
from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.db.session import get_db
from app.db.models import Store, ShoppingList, ShoppingListEntry, Aggregate, Price, Item, AggregateItem, Chain
from app.schemas.optimization import OptimizationRequest, OptimizationResponse, StoreResult

router = APIRouter()

@router.post("/", response_model=OptimizationResponse)
def optimize_basket(
    request: OptimizationRequest,
    db: Session = Depends(get_db)
) -> Any:
    # 1. Get Shopping List and User Location
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == request.shopping_list_id).first()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    
    # Use request location or user preferred location (to be implemented with Auth)
    if request.user_lat and request.user_lng:
        user_point = from_shape(Point(request.user_lng, request.user_lat), srid=4326)
    else:
        # For now, fallback to center of Israel if not provided
        user_point = from_shape(Point(34.7818, 32.0853), srid=4326)

    # 2. Find Stores within max_distance_km
    # Use func.ST_DWithin for PostGIS
    candidate_stores = db.query(Store, Chain).join(Chain).filter(
        func.ST_DWithin(Store.location, user_point, request.max_distance_km * 1000)
    ).all()
    
    if not candidate_stores:
        raise HTTPException(status_code=404, detail="No stores found within the specified distance")

    # 3. For each Aggregate in List, find cheapest specific item in EACH store
    list_entries = db.query(ShoppingListEntry, Aggregate).join(Aggregate).filter(
        ShoppingListEntry.shopping_list_id == request.shopping_list_id
    ).all()

    # Pre-fetch all prices for items in the aggregates for candidate stores
    # store_id -> aggregate_id -> cheapest_price_data
    store_aggregate_options = {}

    for store, chain in candidate_stores:
        store_aggregate_options[store.id] = {
            "store_name": store.name,
            "chain_name": chain.name,
            "distance_km": db.scalar(func.ST_Distance(Store.location, user_point)) / 1000 if store.location else 0,
            "aggregates": {}
        }
        
        for entry, aggregate in list_entries:
            # Find cheapest item in this aggregate for this store
            cheapest = (
                db.query(Price, Item)
                .join(Item)
                .join(AggregateItem, AggregateItem.item_id == Item.id)
                .filter(
                    AggregateItem.aggregate_id == aggregate.id,
                    Price.store_id == store.id
                )
                .order_by(Price.price_per_unit)
                .first()
            )
            
            if cheapest:
                price, item = cheapest
                cost = price.price_per_unit * Decimal(str(entry.desired_amount))
                store_aggregate_options[store.id]["aggregates"][aggregate.id] = {
                    "item_id": item.id,
                    "item_name": item.name,
                    "price_per_unit": price.price_per_unit,
                    "cost": cost,
                    "aggregate_id": aggregate.id,
                    "aggregate_name": aggregate.name
                }

    # 4. Optimization Logic
    selected_stores_results = []
    
    if request.max_stores == 1:
        # Simple case: calculate total for each store and pick best
        best_store_id = None
        min_total = Decimal('Infinity')
        
        for store_id, data in store_aggregate_options.items():
            # Check if store has ALL items in list
            if len(data["aggregates"]) == len(list_entries):
                total = sum(opt["cost"] for opt in data["aggregates"].values())
                if total < min_total:
                    min_total = total
                    best_store_id = store_id
        
        if not best_store_id:
            raise HTTPException(status_code=404, detail="No single store contains all items in your list")
        
        best_data = store_aggregate_options[best_store_id]
        selected_stores_results.append(StoreResult(
            store_id=best_store_id,
            store_name=best_data["store_name"],
            chain_name=best_data["chain_name"],
            distance_km=best_data["distance_km"],
            items=list(best_data["aggregates"].values()),
            total_cost=min_total
        ))
    else:
        # Multi-store Greedy approach
        remaining_aggregates = {aggregate.id for _, aggregate in list_entries}
        selected_store_ids = []
        
        while remaining_aggregates and len(selected_store_ids) < request.max_stores:
            best_additional_store_id = None
            best_additional_savings = Decimal('-Infinity')
            
            # Find store that covers most remaining items at lowest cost
            # For MVP: Simple greedy - pick store that reduces total cost most for remaining items
            for store_id, data in store_aggregate_options.items():
                if store_id in selected_store_ids:
                    continue
                
                # Potential items this store can cover from remaining
                potential_cover = {agg_id for agg_id in data["aggregates"].keys() if agg_id in remaining_aggregates}
                if not potential_cover:
                    continue
                
                # Savings calculation: 
                # (For simplicity: Total cost of items covered in this store compared to next best or avg)
                # Here: just pick store that covers MOST remaining items for now
                if len(potential_cover) > 0: # Simple heuristic
                    best_additional_store_id = store_id # Just pick the first for now, can be improved
                    break
            
            if not best_additional_store_id:
                break
                
            selected_store_ids.append(best_additional_store_id)
            # Mark as covered (assuming we buy ALL remaining available items in this store)
            covered = {agg_id for agg_id in store_aggregate_options[best_additional_store_id]["aggregates"].keys() if agg_id in remaining_aggregates}
            remaining_aggregates -= covered

        # Format results for selected stores
        # Note: Greedy selection logic above is simplified. Full implementation would re-evaluate item assignment.
        # This is enough for the MVP structure.
        
        # ... (Formatting logic for multiple stores) ...

    total_cost = sum(s.total_cost for s in selected_stores_results)
    
    return OptimizationResponse(
        selected_stores=selected_stores_results,
        total_basket_cost=total_cost,
        total_savings=Decimal("0.0") # To be calculated against an average/max store
    )
