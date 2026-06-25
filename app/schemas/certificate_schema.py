from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.schemas.message_schema import MessageRead

# Certificate Schemas
class CertificateBase(BaseModel):
    employee_id: UUID
    module_id: UUID
    verification_code: str

class CertificateCreate(BaseModel):
    employee_id: UUID
    module_id: UUID

class CertificateResponse(CertificateBase):
    id: UUID
    issued_at: datetime

    class Config:
        from_attributes = True


# Reward Schemas
class RewardBase(BaseModel):
    employee_id: UUID
    xp_amount: int
    description: str

class RewardCreate(RewardBase):
    pass

class RewardResponse(RewardBase):
    id: UUID
    earned_at: datetime

    class Config:
        from_attributes = True


# Reported Email Schemas
from typing import Dict, Any

class ReportedEmailBase(BaseModel):
    employee_id: Optional[UUID] = None
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    campaign_id: Optional[UUID] = None
    campaign_name: Optional[str] = None
    email_subject: str
    email_sender: str
    email_body: Optional[str] = None
    report_reason: Optional[str] = None
    report_status: str = "Pending"
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    department_id: Optional[UUID] = None
    report_source: Optional[str] = None
    
    # Kept for compatibility
    reported_by: Optional[UUID] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    email_date: Optional[datetime] = None
    risk_score: int = 0
    risk_level: str = "Low"
    status: str = "Pending"

class ReportedEmailCreate(BaseModel):
    employee_id: UUID
    campaign_id: Optional[UUID] = None
    email_subject: str
    email_sender: str
    email_body: Optional[str] = None
    report_reason: Optional[str] = None

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
    # Keep legacy/optional fields
    email_date: Optional[datetime] = None
    email_body: Optional[str] = None
    reported_by: Optional[UUID] = None

class ReportedEmailUpdate(BaseModel):
    status: str # Pending, Verified Phish, Safe

class ReportedEmailStatusUpdate(BaseModel):
    report_status: str # Pending, Safe, Verified Phish (or Malicious)

class ReportedEmailReview(BaseModel):
    report_status: str # Pending, Safe, Suspicious, Closed

class GmailAdminMessageCreate(BaseModel):
    employee_email: EmailStr
    report_id: UUID
    message: str

class ReportedEmailResponse(ReportedEmailBase):
    id: UUID
    analysis_results: Optional[Dict[str, Any]] = None
    reported_at: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: Optional[List[MessageRead]] = []

    class Config:
        from_attributes = True
