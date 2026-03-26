from typing import Generator, Optional
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User

def get_current_user(
    x_user_email: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Simple dependency to get user from X-User-Email header for testing."""
    if not x_user_email:
        raise HTTPException(status_code=401, detail="X-User-Email header required for test auth")
    
    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")
    
    return user
