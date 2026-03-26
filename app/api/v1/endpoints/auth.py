from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from pydantic import BaseModel, EmailStr
from uuid import UUID

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr

@router.post("/register/", response_model=UserResponse)
def register_user(
    user_in: UserRegister,
    db: Session = Depends(get_db)
) -> Any:
    """Register a user with email only (Test Only)."""
    # ...
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(email=user_in.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/me/", response_model=UserResponse)
def get_user_by_email(
    email: str,
    db: Session = Depends(get_db)
) -> Any:
    """Fetch user info by email (Simple 'Login' for test)."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
