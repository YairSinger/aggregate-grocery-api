from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.db.session import get_db
from app.db.models import Item
from pydantic import BaseModel, ConfigDict
from uuid import UUID

router = APIRouter()

class ItemSchema(BaseModel):
    id: UUID
    item_code: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

@router.get("/search", response_model=List[ItemSchema])
def search_items(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    limit: int = 20
) -> Any:
    """Search for items using fuzzy matching on name and brand."""
    # Using simple ILIKE for MVP. 
    # For production, we'd use pg_trgm and word_similarity.
    search_term = f"%{q}%"
    return db.query(Item).filter(
        or_(
            Item.name.ilike(search_term),
            Item.brand.ilike(search_term)
        )
    ).limit(limit).all()
