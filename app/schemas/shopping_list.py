from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, model_validator
from uuid import UUID

class ShoppingListEntryBase(BaseModel):
    aggregate_id: Optional[UUID] = None
    item_id: Optional[UUID] = None
    desired_amount: float

    @model_validator(mode="after")
    def check_one_of(self):
        if (self.aggregate_id is None) == (self.item_id is None):
            raise ValueError("Exactly one of aggregate_id or item_id must be set")
        return self

class ShoppingListEntryCreate(ShoppingListEntryBase):
    pass

class ShoppingListEntry(ShoppingListEntryBase):
    id: UUID
    shopping_list_id: UUID
    model_config = ConfigDict(from_attributes=True)

class ShoppingListBase(BaseModel):
    name: str

class ShoppingListCreate(ShoppingListBase):
    entries: List[ShoppingListEntryCreate] = []

class ShoppingListUpdate(BaseModel):
    name: Optional[str] = None
    entries: Optional[List[ShoppingListEntryCreate]] = None

class ShoppingList(ShoppingListBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    entries: List[ShoppingListEntry] = []
    model_config = ConfigDict(from_attributes=True)
