from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

class ReportedEmailBase(BaseModel):
    employee_id: UUID
    employee_name: str
    employee_email: str
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = None
    email_subject: str
    sender_email: str
    email_body: str
    threat_score: int
    report_reason: str
    report_status: Optional[str] = "Pending"

class ReportedEmailCreate(ReportedEmailBase):
    pass

class ReportedEmailRead(ReportedEmailBase):
    id: UUID
    reported_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None

    class Config:
        orm_mode = True

class ReportedEmailUpdate(BaseModel):
    report_status: str
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
