from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class ShoppingListEntryBase(BaseModel):
    aggregate_id: UUID
    desired_amount: float

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
