from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

# Notification Schemas
class NotificationBase(BaseModel):
    user_id: Optional[UUID] = None
    employee_id: Optional[UUID] = None
    title: str
    message: str
    is_read: bool = False
    notification_type: Optional[str] = "info"

class NotificationCreate(NotificationBase):
    pass

class NotificationResponse(NotificationBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Audit Log Schemas
class AuditLogCreate(BaseModel):
    action: str
    details: Optional[str] = None

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    action: str
    details: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# Security Score Schemas
class SecurityScoreResponse(BaseModel):
    id: UUID
    employee_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    score: float
    recorded_at: datetime

    class Config:
        from_attributes = True
