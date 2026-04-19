from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db.session import get_db
from app.db.models import Item
from app.schemas.item import Item as ItemSchema

router = APIRouter()

@router.get("/search", response_model=List[ItemSchema])
def search_items(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    limit: int = 20
) -> Any:
    """Search for items using fuzzy matching on name and brand."""
    search_term = f"%{q}%"
    return db.query(Item).filter(
        or_(
            Item.name.ilike(search_term),
            Item.brand.ilike(search_term)
        )
    ).limit(limit).all()
