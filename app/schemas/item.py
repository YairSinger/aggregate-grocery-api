from typing import Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from app.db.models import UnitOfMeasure

class ItemBase(BaseModel):
    item_code: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: UnitOfMeasure
    quantity: float

class Item(ItemBase):
    id: UUID
    model_config = ConfigDict(from_attributes=True)
