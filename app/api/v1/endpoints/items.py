from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from pydantic import BaseModel
from uuid import UUID
from app.db.session import get_db
from app.db.models import Item, Price, Store, Chain
from app.schemas.item import Item as ItemSchema

router = APIRouter()


class ItemRow(BaseModel):
    id: UUID
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    unit_of_measure: str
    quantity: float
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price_per_unit: Optional[float] = None
    best_chain: Optional[str] = None
    store_count: int = 0

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ItemRow])
def list_items(
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    sort_by: str = "name",
    sort_dir: str = "asc",
    limit: int = Query(default=100, le=500),
    offset: int = 0,
) -> Any:
    """List items with aggregated price info across stores."""
    # Subquery: min/max price and store count per item
    price_agg = (
        db.query(
            Price.item_id,
            func.min(Price.effective_price).label("min_price"),
            func.max(Price.effective_price).label("max_price"),
            func.min(Price.price_per_unit).label("price_per_unit"),
            func.count(Price.store_id.distinct()).label("store_count"),
        )
        .group_by(Price.item_id)
        .subquery()
    )

    # Subquery: chain name for the cheapest price
    best_chain_sub = (
        db.query(
            Price.item_id,
            Chain.name.label("chain_name"),
        )
        .join(Store, Price.store_id == Store.id)
        .join(Chain, Store.chain_id == Chain.id)
        .distinct(Price.item_id)
        .order_by(Price.item_id, Price.effective_price.asc())
        .subquery()
    )

    query = (
        db.query(
            Item,
            price_agg.c.min_price,
            price_agg.c.max_price,
            price_agg.c.price_per_unit,
            price_agg.c.store_count,
            best_chain_sub.c.chain_name,
        )
        .outerjoin(price_agg, Item.id == price_agg.c.item_id)
        .outerjoin(best_chain_sub, Item.id == best_chain_sub.c.item_id)
    )

    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(Item.name.ilike(term), Item.brand.ilike(term), Item.category.ilike(term))
        )

    sort_col = {
        "name": Item.name,
        "brand": Item.brand,
        "category": Item.category,
        "min_price": price_agg.c.min_price,
        "price_per_unit": price_agg.c.price_per_unit,
        "store_count": price_agg.c.store_count,
    }.get(sort_by, Item.name)

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    rows = query.offset(offset).limit(limit).all()

    return [
        ItemRow(
            id=item.id,
            name=item.name,
            brand=item.brand,
            category=item.category,
            unit_of_measure=item.unit_of_measure.value,
            quantity=item.quantity,
            min_price=float(min_price) if min_price is not None else None,
            max_price=float(max_price) if max_price is not None else None,
            price_per_unit=float(ppu) if ppu is not None else None,
            best_chain=chain_name,
            store_count=store_count or 0,
        )
        for item, min_price, max_price, ppu, store_count, chain_name in rows
    ]


@router.get("/search", response_model=List[ItemSchema])
def search_items(
    q: str = Query(..., min_length=2),
    db: Session = Depends(get_db),
    limit: int = 20,
) -> Any:
    """Search items by name or brand."""
    term = f"%{q}%"
    return (
        db.query(Item)
        .filter(or_(Item.name.ilike(term), Item.brand.ilike(term)))
        .limit(limit)
        .all()
    )
