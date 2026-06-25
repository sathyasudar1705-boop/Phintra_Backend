from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification_schema import NotificationCreate, NotificationResponse
from app.dependencies import get_current_user, require_manager, require_employee
from uuid import UUID
from typing import List

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """Retrieve active notifications for logged-in user (Employees, Managers, Admins)."""
    # If admin/manager, show user_id matching notifications.
    # Otherwise, check employee or user. Let's filter by current user's ID
    return db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).all()

@router.put("/{id}/read", response_model=NotificationResponse)
def mark_notification_as_read(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """Mark notification as read (Employees, Managers, Admins)."""
    notif = db.query(Notification).filter(Notification.id == id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(notif_in: NotificationCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Dispatch manual alert notification (Managers & Admins)."""
    db_notif = Notification(**notif_in.dict())
    db.add(db_notif)
    db.commit()
    db.refresh(db_notif)
    return db_notif
