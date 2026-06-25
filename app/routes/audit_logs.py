from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.notification_schema import AuditLogResponse, AuditLogCreate
from app.dependencies import require_admin, require_employee
from typing import List

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Retrieve history of administrative and configuration operations (Admin only)."""
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()

@router.post("", response_model=AuditLogResponse, status_code=status.HTTP_201_CREATED)
def create_audit_log_route(req: AuditLogCreate, db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """Manually append an operation event entry to platform audit history (Employees, Managers, Admins)."""
    db_log = AuditLog(
        user_id=current_user.id,
        action=req.action,
        details=req.details
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
