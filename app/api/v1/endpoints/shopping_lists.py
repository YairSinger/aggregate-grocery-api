from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import ShoppingList, ShoppingListEntry
from app.schemas import shopping_list as schemas

router = APIRouter()

from app.api.deps import get_current_user
from app.db.models import User

router = APIRouter()

@router.get("/", response_model=List[schemas.ShoppingList])
def read_shopping_lists(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Retrieve all user shopping lists."""
    return db.query(ShoppingList).filter(ShoppingList.user_id == current_user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.ShoppingList)
def create_shopping_list(
    list_in: schemas.ShoppingListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new shopping list and its aggregate entries."""
    shopping_list = ShoppingList(user_id=current_user.id, name=list_in.name)
    db.add(shopping_list)
    db.flush()

    for entry in list_in.entries:
        db.add(ShoppingListEntry(
            shopping_list_id=shopping_list.id,
            aggregate_id=entry.aggregate_id,
            desired_amount=entry.desired_amount
        ))
    
    db.commit()
    db.refresh(shopping_list)
    return shopping_list

@router.get("/{id}", response_model=schemas.ShoppingList)
def read_shopping_list(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Retrieve a specific shopping list."""
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == id, ShoppingList.user_id == current_user.id).first()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    return shopping_list

@router.delete("/{id}", response_model=schemas.ShoppingList)
def delete_shopping_list(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete a shopping list and its entries."""
    shopping_list = db.query(ShoppingList).filter(ShoppingList.id == id, ShoppingList.user_id == current_user.id).first()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="Shopping list not found")
    
    db.query(ShoppingListEntry).filter(ShoppingListEntry.shopping_list_id == id).delete()
    db.delete(shopping_list)
    db.commit()
    return shopping_list
