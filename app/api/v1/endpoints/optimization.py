from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.optimization import (
    AlternativeStore,
    OptimizationRequest,
    OptimizationResponse,
    StoreResult,
)
from app.services.basket_optimizer import optimize_single_store
from app.services.loaders.shopping_list_loader import load_wanted_items

router = APIRouter()

# Default fallback location: centre of Israel
_DEFAULT_LAT = 32.0853
_DEFAULT_LNG = 34.7818


@router.post("/", response_model=OptimizationResponse)
def optimize_basket(
    request: OptimizationRequest,
    db: Session = Depends(get_db),
) -> Any:
    user_lat = request.user_lat or _DEFAULT_LAT
    user_lng = request.user_lng or _DEFAULT_LNG

    try:
        wanted = load_wanted_items(
            db=db,
            shopping_list_id=request.shopping_list_id,
            user_lat=user_lat,
            user_lng=user_lng,
            max_distance_km=request.max_distance_km,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    result = optimize_single_store(wanted)

    if result.store_id is None:
        raise HTTPException(
            status_code=404,
            detail="No nearby store has any of the items in your list",
        )

    return OptimizationResponse(
        selected_stores=[
            StoreResult(
                store_id=result.store_id,
                store_name=result.store_name,
                chain_name=result.chain_name,
                distance_km=result.distance_km,
                items=[
                    {
                        "aggregate_id": str(item.aggregate_id) if item.aggregate_id else None,
                        "aggregate_name": item.name,
                        "item_id": str(item.item_id),
                        "item_name": item.item_name,
                        "price_per_unit": float(item.price_per_unit),
                        "desired_amount": float(item.packages_needed),
                        "cost": float(item.cost),
                    }
                    for item in result.assigned_items
                ],
                total_cost=result.total_cost,
            )
        ],
        total_basket_cost=result.total_cost,
        total_savings=(
            result.alternatives[0].total_cost - result.total_cost
            if result.alternatives
            else result.total_cost  # no alternative found — savings unknown
        ),
        alternatives=[
            AlternativeStore(
                store_name=alt.store_name,
                chain_name=alt.chain_name,
                total_cost=alt.total_cost,
            )
            for alt in result.alternatives[:2]
        ],
        unresolved=[
            {"name": w.name, "desired_amount": w.desired_amount, "unit": w.unit}
            for w in result.unresolved
        ],
    )
