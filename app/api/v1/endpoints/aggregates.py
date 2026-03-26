from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Aggregate, AggregateItem, Item, User
from app.schemas import aggregate as schemas

router = APIRouter()

from app.api.deps import get_current_user

router = APIRouter()

@router.get("/", response_model=List[schemas.Aggregate])
def read_aggregates(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
) -> Any:
    """Retrieve all user-defined aggregates."""
    return db.query(Aggregate).filter(Aggregate.user_id == current_user.id).offset(skip).limit(limit).all()

@router.post("/", response_model=schemas.Aggregate)
def create_aggregate(
    aggregate_in: schemas.AggregateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Create a new aggregate and add items to it."""
    # Check if items already exist in other aggregates for this user
    existing_items = (
        db.query(AggregateItem)
        .join(Aggregate)
        .filter(
            Aggregate.user_id == current_user.id,
            AggregateItem.item_id.in_(aggregate_in.item_ids)
        )
        .all()
    )
    if existing_items:
        raise HTTPException(
            status_code=400, 
            detail="One or more items already belong to another aggregate."
        )

    aggregate = Aggregate(
        user_id=current_user.id,
        name=aggregate_in.name,
        description=aggregate_in.description,
        unit_of_measure=aggregate_in.unit_of_measure
    )
    db.add(aggregate)
    db.flush()

    for item_id in aggregate_in.item_ids:
        db.add(AggregateItem(aggregate_id=aggregate.id, item_id=item_id))
    
    db.commit()
    db.refresh(aggregate)
    return aggregate

@router.get("/{id}", response_model=schemas.Aggregate)
def read_aggregate(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Retrieve a specific aggregate."""
    aggregate = db.query(Aggregate).filter(Aggregate.id == id, Aggregate.user_id == current_user.id).first()
    if not aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    return aggregate

@router.put("/{id}", response_model=schemas.Aggregate)
def update_aggregate(
    id: UUID,
    aggregate_in: schemas.AggregateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Update an aggregate's details and items."""
    aggregate = db.query(Aggregate).filter(Aggregate.id == id, Aggregate.user_id == current_user.id).first()
    if not aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")

    update_data = aggregate_in.model_dump(exclude_unset=True)
    item_ids = update_data.pop("item_ids", None)

    for field, value in update_data.items():
        setattr(aggregate, field, value)

    if item_ids is not None:
        db.query(AggregateItem).filter(AggregateItem.aggregate_id == id).delete()
        for item_id in item_ids:
            db.add(AggregateItem(aggregate_id=id, item_id=item_id))

    db.commit()
    db.refresh(aggregate)
    return aggregate

@router.delete("/{id}", response_model=schemas.Aggregate)
def delete_aggregate(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """Delete an aggregate and its item links."""
    aggregate = db.query(Aggregate).filter(Aggregate.id == id, Aggregate.user_id == current_user.id).first()
    if not aggregate:
        raise HTTPException(status_code=404, detail="Aggregate not found")
    
    db.query(AggregateItem).filter(AggregateItem.aggregate_id == id).delete()
    db.delete(aggregate)
    db.commit()
    return aggregate
