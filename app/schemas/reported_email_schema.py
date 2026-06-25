from datetime import datetime
from typing import Optional, Any, Dict, List
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr

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
        from_attributes = True

class ReportedEmailUpdate(BaseModel):
    report_status: str
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None

class GmailReportEmailCreate(BaseModel):
    subject: str
    sender: str
    body: Optional[str] = None
    reported_user_email: Optional[str] = None
    reported_time: Optional[str] = None
    employee_email: Optional[str] = None
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    reported_at: Optional[str] = None
    email_date: Optional[datetime] = None
    email_body: Optional[str] = None
    reported_by: Optional[UUID] = None

class GmailAdminMessageCreate(BaseModel):
    employee_email: EmailStr
    report_id: UUID
    message: str
