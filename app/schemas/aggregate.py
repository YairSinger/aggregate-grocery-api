from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from app.db.models import UnitOfMeasure
from app.schemas.item import Item

class AggregateItemBase(BaseModel):
    item_id: UUID

class AggregateItemCreate(AggregateItemBase):
    pass

class AggregateItem(AggregateItemBase):
    id: UUID
    aggregate_id: UUID
    item: Item
    model_config = ConfigDict(from_attributes=True)

class AggregateBase(BaseModel):
    name: str
    description: Optional[str] = None
    unit_of_measure: UnitOfMeasure

class AggregateCreate(AggregateBase):
    item_ids: List[UUID] = []

class AggregateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    unit_of_measure: Optional[UnitOfMeasure] = None
    item_ids: Optional[List[UUID]] = None

class Aggregate(AggregateBase):
    id: UUID
    user_id: UUID
    items: List[AggregateItem] = []
    model_config = ConfigDict(from_attributes=True)
