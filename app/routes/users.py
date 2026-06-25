from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user_schema import UserCreate, UserUpdate, UserResponse
from app.dependencies import require_admin
from app.utils.security import hash_password
from uuid import UUID
from typing import List

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """List all portal users (Admin only)."""
    return db.query(User).all()

@router.get("/{id}", response_model=UserResponse)
def get_user(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Get single user details by UUID (Admin only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Create a new portal user account (Admin only)."""
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User email already registered")
        
    db_user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=user_in.is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/{id}", response_model=UserResponse)
def update_user(id: UUID, user_in: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Modify details of user account (Admin only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = user_in.dict(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        user.hashed_password = hash_password(update_data["password"])
        del update_data["password"]
        
    for key, val in update_data.items():
        setattr(user, key, val)
        
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_user(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Delete a user account from database (Admin only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"detail": "User successfully deleted"}
