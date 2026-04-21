from typing import List, Optional, Dict
from pydantic import BaseModel
from uuid import UUID
from decimal import Decimal

class OptimizationRequest(BaseModel):
    shopping_list_id: UUID
    max_distance_km: float = 5.0
    max_stores: int = 1
    user_lat: Optional[float] = None
    user_lng: Optional[float] = None

class StoreResult(BaseModel):
    store_id: UUID
    store_name: str
    chain_name: str
    distance_km: float
    items: List[Dict]
    total_cost: Decimal

class AlternativeStore(BaseModel):
    store_name: str
    chain_name: str
    total_cost: Decimal

class OptimizationResponse(BaseModel):
    selected_stores: List[StoreResult]
    total_basket_cost: Decimal
    total_savings: Decimal
    alternatives: List[AlternativeStore] = []
